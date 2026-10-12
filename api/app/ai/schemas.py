"""Typed outputs of the AI agents.

These classes are the agents' `output_type`. Pydantic AI turns them into the
schema the model has to fill in, validates the reply against them and asks the
model to try again on a mismatch. The app only ever sees validated instances;
nothing parses model text. Field descriptions are part of the prompt, so they
are written as instructions to the model.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

FindingCategory = Literal[
    "not_verifiable",
    "missing_why",
    "missing_go_to_market",
    "scope_too_big",
    "carry_over",
]


class ReviewFinding(BaseModel):
    task_key: str | None = Field(
        description=(
            "Key of the task this finding is about, copied exactly from the plan "
            "(e.g. 'T2'). Use the main task's key for missing_why. Null only for "
            "missing_go_to_market."
        )
    )
    category: FindingCategory = Field(
        description=(
            "not_verifiable: describes work to do instead of a result you can check. "
            "missing_why: the main task doesn't say why it matters. "
            "missing_go_to_market: nothing puts this week's work in front of users. "
            "scope_too_big: can't realistically ship within one week. "
            "carry_over: repeats unfinished work from the member's previous plans."
        )
    )
    problem: str = Field(
        description=(
            "One sentence, specific to this task, saying what a demanding lead "
            "would object to. Quote the task's words where it helps; never refer "
            "to it by its key."
        )
    )
    suggested_rewrite: str = Field(
        description=(
            "The exact text to apply with one click, in the member's voice, under "
            "120 characters. For not_verifiable, scope_too_big and carry_over: the "
            "rewritten task title. For missing_why: the why-it-matters sentence. "
            "For missing_go_to_market: the title of a new go-to-market task."
        )
    )


class PlanReview(BaseModel):
    verdict: Literal["ready", "needs_work"] = Field(
        description=(
            "'ready' only if a demanding lead would approve the plan as written; "
            "otherwise 'needs_work'."
        )
    )
    summary: str = Field(
        description=(
            "One or two direct, constructive sentences: the overall call and the "
            "single most important fix. Refer to tasks by their words, never by "
            "their keys."
        )
    )
    findings: list[ReviewFinding] = Field(
        description="At most 6 findings, most important first. Empty if ready."
    )


class PlanDraft(BaseModel):
    main_task: str = Field(
        description=(
            "The one significant thing to ship this week, written as a result you "
            "can check (what will be true, and how it's confirmed)."
        )
    )
    why_it_matters: str = Field(
        description="One sentence on why the main task matters to users or the business."
    )
    sub_goals: list[str] = Field(
        description="2 to 5 smaller results that get the main task over the line."
    )
    go_to_market: list[str] = Field(
        description=(
            "1 to 3 tasks that put this week's work in front of users: changelog "
            "entry, announcement, analytics events, onboarding, docs or a feature "
            "flag rollout."
        )
    )
    left_out: list[str] = Field(
        description=(
            "Things from the notes that don't belong in this week's plan, briefly "
            "rephrased so nothing is lost. Empty if everything fits."
        )
    )
    open_questions: list[str] = Field(
        description=(
            "Up to 3 short questions where the notes are ambiguous and the answer "
            "would change the plan. Empty if none."
        )
    )


class PreviousPlan(BaseModel):
    """What the look-back tool tells the reviewer about one earlier week."""

    week_start: date
    status: str
    main_task: str
    main_task_shipped: bool | None
    unfinished_tasks: list[str]
    # The member's own words when they closed the week ("the refactor took
    # longer than planned"), so a carry-over finding can say what happened.
    outcome_note: str | None
