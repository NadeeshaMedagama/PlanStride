"""Runs the AI agents on behalf of an API request.

Every run goes through `AIService._run`, which:
- throttles per user, so one member can't burn the organization's free-tier
  quota, and never fires without an explicit request from the UI;
- bounds the whole run with a timeout, so a slow model can't hang the page;
- maps every failure (429, timeout, outage, invalid output, no key) to a plain
  message the UI shows as is, while the plan itself is never touched;
- records one usage event against the organization, success or not.

The agents' validated output is then normalized into what the app acts on:
review findings tied to real task keys with a known "apply" action, and a
draft whose lists fit the plan form. Nothing here writes a plan.
"""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, NamedTuple

from pydantic_ai import AgentRunResult, UsageLimits
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents import (
    KeyedTask,
    ReviewDeps,
    continues_unfinished_work,
    format_notes_for_draft,
    format_plan_for_review,
    model_key,
    plan_drafter,
    plan_reviewer,
)
from app.ai.schemas import FindingCategory, PlanDraft, PlanReview, PreviousPlan
from app.config import settings
from app.domain import (
    MAX_GO_TO_MARKET_GOALS,
    MAX_SUB_GOALS,
    AIErrorType,
    AIFeature,
    TaskKind,
    utcnow,
)
from app.exceptions import APIException
from app.logging import logger
from app.services.ai_usage import AIUsageService
from app.tenancy import OrgAccess

# A review makes at most: one look-back tool call, one answer, two retries.
RUN_LIMITS = UsageLimits(request_limit=5)
MAX_FINDINGS = 6
TITLE_MAX_LENGTH = 200
WHY_MAX_LENGTH = 1000

FindingAction = Literal["replace_title", "set_why", "add_go_to_market"]


class _FailureReply(NamedTuple):
    status_code: int
    code: str
    message: str


_FAILURES: dict[AIErrorType, _FailureReply] = {
    "throttled": _FailureReply(
        429,
        "AI_THROTTLED",
        (
            "You've asked the AI several times in the last minute. Give it a "
            "moment, then try again."
        ),
    ),
    "provider_rate_limit": _FailureReply(
        429,
        "AI_RATE_LIMITED",
        (
            "The AI is getting more requests than it can take right now. Nothing "
            "in your plan changed; try again in a minute or carry on without it."
        ),
    ),
    "timeout": _FailureReply(
        504,
        "AI_TIMEOUT",
        (
            "The AI took too long to answer, so we stopped waiting. Nothing in "
            "your plan changed; try again or carry on without it."
        ),
    ),
    "provider_error": _FailureReply(
        503,
        "AI_UNAVAILABLE",
        (
            "The AI service isn't responding right now. Nothing in your plan "
            "changed; you can keep planning without it."
        ),
    ),
    "invalid_output": _FailureReply(
        502,
        "AI_INVALID_OUTPUT",
        (
            "The AI's answer didn't come back in a shape we could use. Nothing in "
            "your plan changed; try again."
        ),
    ),
    "not_configured": _FailureReply(
        503,
        "AI_NOT_CONFIGURED",
        (
            "AI help isn't set up on this server yet. You can still write, save "
            "and submit your plan as normal."
        ),
    ),
    "internal_error": _FailureReply(
        503,
        "AI_FAILED",
        (
            "Something went wrong while asking the AI. Nothing in your plan "
            "changed; try again."
        ),
    ),
}


@dataclass(frozen=True)
class AIFailure:
    error_type: AIErrorType

    def to_exception(self) -> APIException:
        reply = _FAILURES[self.error_type]
        return APIException(
            status_code=reply.status_code, code=reply.code, message=reply.message
        )


@dataclass(frozen=True)
class ReviewTaskInput:
    """A task as the plan editor holds it; `key` is the editor's own id."""

    key: str
    kind: TaskKind
    title: str


@dataclass(frozen=True)
class ReviewedFinding:
    task_key: str | None
    category: FindingCategory
    problem: str
    suggested_rewrite: str
    action: FindingAction


@dataclass(frozen=True)
class ReviewResult:
    verdict: Literal["ready", "needs_work"]
    summary: str
    findings: list[ReviewedFinding]


class AIService:
    def __init__(self, session: AsyncSession, model: Model | None):
        self.session = session
        self.model = model

    async def review_plan(
        self,
        access: OrgAccess,
        *,
        week_start: date,
        why_it_matters: str | None,
        tasks: Sequence[ReviewTaskInput],
    ) -> ReviewResult | AIFailure:
        ordered = sorted(tasks, key=lambda task: _KIND_ORDER[task.kind])
        keyed = [
            KeyedTask(key=f"T{index}", kind=task.kind, title=task.title)
            for index, task in enumerate(ordered, start=1)
        ]
        editor_keys = {
            keyed_task.key: task.key for keyed_task, task in zip(keyed, ordered)
        }
        prompt = format_plan_for_review(
            week_start=week_start, why_it_matters=why_it_matters, tasks=keyed
        )
        deps = ReviewDeps(
            session=self.session,
            organization_id=access.organization_id,
            user_id=access.user_id,
            week_start=week_start,
            task_titles={task.key: task.title for task in keyed},
        )
        output = await self._run(
            access,
            "plan_review",
            lambda model: plan_reviewer.run(
                prompt, deps=deps, model=model, usage_limits=RUN_LIMITS
            ),
        )
        if isinstance(output, AIFailure):
            return output
        return normalize_review(output, keyed, editor_keys, deps.looked_back or [])

    async def draft_plan(
        self, access: OrgAccess, *, week_start: date, notes: str
    ) -> PlanDraft | AIFailure:
        prompt = format_notes_for_draft(week_start=week_start, notes=notes)
        output = await self._run(
            access,
            "plan_draft",
            lambda model: plan_drafter.run(
                prompt, model=model, usage_limits=RUN_LIMITS
            ),
        )
        if isinstance(output, AIFailure):
            return output
        return normalize_draft(output)

    async def _run[T](
        self,
        access: OrgAccess,
        feature: AIFeature,
        run: Callable[[Model], Awaitable[AgentRunResult[T]]],
    ) -> T | AIFailure:
        # Captured up front: a rollback below expires ORM objects.
        organization_id, user_id = access.organization_id, access.user_id
        model_name = self.model.model_name if self.model else settings.AI_MODEL
        usage = AIUsageService(self.session)

        async def record_failure(
            error_type: AIErrorType, latency_ms: int | None = None
        ):
            outcome = "rate_limited" if error_type in _RATE_LIMITS else "failed"
            await usage.record(
                organization_id=organization_id,
                user_id=user_id,
                feature=feature,
                outcome=outcome,
                error_type=error_type,
                model_name=model_name,
                latency_ms=latency_ms,
            )
            return AIFailure(error_type)

        recent = await usage.recent_requests(
            user_id, since=utcnow() - timedelta(minutes=1)
        )
        if recent >= settings.AI_REQUESTS_PER_USER_PER_MINUTE:
            return await record_failure("throttled")
        if self.model is None:
            return await record_failure("not_configured")

        started = time.perf_counter()
        try:
            async with asyncio.timeout(settings.AI_TIMEOUT_SECONDS):
                result = await run(self.model)
        except Exception as exc:
            latency_ms = _elapsed_ms(started)
            error_type = classify_failure(exc)
            # Log the cause for operators; never the plan or notes themselves.
            logger.warning(
                "AI %s failed for organization %s: %s (%s)",
                feature,
                organization_id,
                error_type,
                type(exc).__name__,
                exc_info=error_type in ("provider_error", "internal_error"),
            )
            if error_type in ("timeout", "internal_error"):
                # A cancelled or failed tool query can leave the transaction
                # aborted; start clean so the usage event can still be written.
                await self.session.rollback()
            return await record_failure(error_type, latency_ms)

        run_usage = result.usage
        await usage.record(
            organization_id=organization_id,
            user_id=user_id,
            feature=feature,
            outcome="success",
            model_name=model_name,
            latency_ms=_elapsed_ms(started),
            input_tokens=run_usage.input_tokens,
            output_tokens=run_usage.output_tokens,
        )
        return result.output


_KIND_ORDER: dict[TaskKind, int] = {"main": 0, "sub_goal": 1, "go_to_market": 2}
_RATE_LIMITS: frozenset[AIErrorType] = frozenset({"throttled", "provider_rate_limit"})
_ACTIONS: dict[FindingCategory, FindingAction] = {
    "not_verifiable": "replace_title",
    "scope_too_big": "replace_title",
    "carry_over": "replace_title",
    "missing_why": "set_why",
    "missing_go_to_market": "add_go_to_market",
}
# A task gets one title rewrite. When the model offers several, the more
# specific diagnosis wins: work that keeps carrying over, or that can't fit in
# a week, says more than "not a checkable result".
_TITLE_PRIORITY: dict[FindingCategory, int] = {
    "carry_over": 0,
    "scope_too_big": 1,
    "not_verifiable": 2,
}


def classify_failure(exc: BaseException) -> AIErrorType:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ModelHTTPError):
        return "provider_rate_limit" if exc.status_code == 429 else "provider_error"
    if isinstance(exc, UnexpectedModelBehavior | UsageLimitExceeded):
        return "invalid_output"
    if isinstance(exc, ModelAPIError):
        return "provider_error"
    return "internal_error"


def normalize_review(
    review: PlanReview,
    keyed: Sequence[KeyedTask],
    editor_keys: dict[str, str],
    history: Sequence[PreviousPlan] = (),
) -> ReviewResult:
    """Keep only findings the app can act on, tied to tasks that exist.

    Schema validation guarantees the shape; this guards the meaning: a finding
    must point at a real task (or none, for a missing go-to-market goal), a
    carry-over must be backed by the unfinished work in `history` (what the
    look-back tool returned), a suggestion must change something without
    duplicating another task, each task gets at most one suggestion per action
    (one title rewrite, one reason), and the text never shows the short keys
    the model works with.
    """
    titles = {task.key: task.title for task in keyed}
    main_key = next(task.key for task in keyed if task.kind == "main")
    # Keyed by what applying the finding changes; a dict keeps the model's
    # order even when a later, more specific finding takes a slot over.
    kept: dict[tuple[str | None, FindingAction], ReviewedFinding] = {}

    for finding in review.findings:
        category = finding.category
        action = _ACTIONS[category]
        key = model_key(finding.task_key)
        if category == "missing_go_to_market":
            key = None
        elif category == "missing_why":
            key = main_key
        elif key not in titles:
            if category != "scope_too_big":
                continue  # points at a task that doesn't exist
            key = main_key
        if category == "carry_over" and not (
            key is not None and continues_unfinished_work(titles[key], history)
        ):
            continue  # nothing the member left unfinished looks like this task

        if action == "set_why":
            rewrite = _clean(finding.suggested_rewrite, WHY_MAX_LENGTH)
        else:
            rewrite = _clean_title(finding.suggested_rewrite)
        problem = _clean(unkey(finding.problem, keyed, own_key=key), 400)
        if not rewrite or not problem:
            continue
        if (
            key is not None
            and action == "replace_title"
            and rewrite.casefold() == titles[key].casefold()
        ):
            continue  # suggests what's already there

        earlier = kept.get((key, action))
        if earlier is not None and _TITLE_PRIORITY.get(
            category, 0
        ) >= _TITLE_PRIORITY.get(earlier.category, 0):
            continue  # this task already has an equally specific suggestion
        kept[(key, action)] = ReviewedFinding(
            task_key=editor_keys[key] if key is not None else None,
            category=category,
            problem=problem,
            suggested_rewrite=rewrite,
            action=action,
        )

    # Applying a suggestion must never leave two tasks with the same title.
    taken = {title.casefold() for title in titles.values()}
    findings: list[ReviewedFinding] = []
    for finding in kept.values():
        if finding.action != "set_why":
            title = finding.suggested_rewrite.casefold()
            if title in taken:
                continue
            taken.add(title)
        findings.append(finding)

    return ReviewResult(
        verdict=review.verdict,
        summary=_clean(unkey(review.summary, keyed), 600),
        findings=findings[:MAX_FINDINGS],
    )


def normalize_draft(draft: PlanDraft) -> PlanDraft:
    """Trim the draft to what the plan form holds."""
    return PlanDraft(
        main_task=_clean_title(draft.main_task),
        why_it_matters=_clean(draft.why_it_matters, WHY_MAX_LENGTH),
        sub_goals=_clean_titles(draft.sub_goals, MAX_SUB_GOALS),
        go_to_market=_clean_titles(draft.go_to_market, MAX_GO_TO_MARKET_GOALS),
        left_out=_clean_lines(draft.left_out, 8),
        open_questions=_clean_lines(draft.open_questions, 3),
    )


_KEY = r"T\d{1,2}"
_KEY_IN_PARENS = re.compile(rf"\s*\(({_KEY})\)")
_KEY_RANGE = re.compile(rf"\b({_KEY})\s*(?:-|–|—|to)\s*({_KEY})\b")
_KEY_MENTION = re.compile(rf"(?i:\btasks?\s+)?\b({_KEY})\b(:?\s*)")
_OWN_TASK: dict[TaskKind, str] = {
    "main": "the main task",
    "sub_goal": "this sub-goal",
    "go_to_market": "this go-to-market goal",
}


def unkey(text: str, keyed: Sequence[KeyedTask], own_key: str | None = None) -> str:
    """Put task keys that leaked into the model's prose back into words.

    The model points at tasks by short keys ("T2") and, despite its
    instructions, sometimes writes them into a sentence. The member never sees
    the keys, so "(T2)" is dropped, and so is a key right before the task's own
    words; a range ("T1-T4") becomes "the tasks"; the finding's own task
    becomes "this sub-goal" (or "the main task"); any other key becomes the
    task's quoted title. A key that also appears in a real title (a "T3"
    instance type, say) is left alone.
    """
    tasks = {
        task.key: task
        for task in keyed
        if not any(re.search(rf"\b{task.key}\b", other.title) for other in keyed)
    }

    def capitalized(match: re.Match[str], words: str) -> str:
        before = match.string[: match.start()].rstrip()
        at_sentence_start = not before or before[-1] in ".!?"
        return words[:1].upper() + words[1:] if at_sentence_start else words

    def in_parens(match: re.Match[str]) -> str:
        return "" if match.group(1) in tasks else match.group(0)

    def key_range(match: re.Match[str]) -> str:
        # The model may miscount ("T1-T9" in a five-task plan); one real key
        # is enough to know it means the plan's tasks.
        if match.group(1) in tasks or match.group(2) in tasks:
            return capitalized(match, "the tasks")
        return match.group(0)

    def mention(match: re.Match[str]) -> str:
        task = tasks.get(match.group(1))
        if task is None:
            return match.group(0)
        following = match.string[match.end() :].lstrip("\"'“‘(").casefold()
        if following.startswith(task.title.casefold()):
            return ""  # "T2 'Write tests' is..." -> "'Write tests' is..."
        words = _OWN_TASK[task.kind] if task.key == own_key else f"“{task.title}”"
        return capitalized(match, words) + match.group(2)

    text = _KEY_IN_PARENS.sub(in_parens, text)
    text = _KEY_RANGE.sub(key_range, text)
    return _KEY_MENTION.sub(mention, text)


_WRAPPING_QUOTES = {'"': '"', "'": "'", "“": "”", "‘": "’"}


def _clean(text: str, max_length: int) -> str:
    """Collapse whitespace and drop quotes wrapped around the whole text (a
    quoted phrase inside it is left alone)."""
    text = " ".join(text.split())
    if len(text) >= 2 and _WRAPPING_QUOTES.get(text[0]) == text[-1]:
        text = text[1:-1].strip()
    return text[:max_length].rstrip()


def _clean_title(text: str) -> str:
    return _clean(text, TITLE_MAX_LENGTH).rstrip(".").rstrip()


def _clean_titles(items: Sequence[str], limit: int) -> list[str]:
    return _dedupe([_clean_title(item) for item in items])[:limit]


def _clean_lines(items: Sequence[str], limit: int) -> list[str]:
    return _dedupe([_clean(item, 300) for item in items])[:limit]


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            unique.append(item)
    return unique


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
