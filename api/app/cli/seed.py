"""Demo data for exploring PlanStride locally (`uv run manage.py seed`).

Three organizations: Northwind Labs and Lumen Health in normal use, and
Brightline Studio, suspended by staff. Each has teams, members in every role
and six weeks of plans dated relative to today, so the demo always shows a live
week: plans awaiting review, approved plans mid-way through, a draft with vague
tasks for the AI reviewer to pick apart, a plan sent back with a comment, and a
history of shipped and unshipped weeks. A deactivated account, a platform staff
user and a known invite link round it out.

The AI usage rows are synthetic, so the internal console's usage view has
something to show before anyone has added a Gemini key.
"""

import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    INVITATION_TTL,
    AIErrorType,
    AIFeature,
    AIOutcome,
    OrgRole,
    PlanStatus,
    TaskKind,
    current_week_start,
    utcnow,
)
from app.models import (
    AIUsageEvent,
    Base,
    Invitation,
    Membership,
    Organization,
    PlanTask,
    Team,
    TeamMembership,
    User,
    WeeklyPlan,
)
from app.security import hash_invite_token, hash_password

DEMO_PASSWORD = "planstride-demo"
DEMO_INVITE_TOKEN = "demo-join-northwind"
WEEKS_OF_HISTORY = 6


@dataclass(frozen=True)
class Content:
    main: str
    why: str | None
    sub_goals: tuple[str, ...]
    go_to_market: tuple[str, ...] = ()


@dataclass(frozen=True)
class Person:
    key: str
    first_name: str
    last_name: str
    role: OrgRole
    plans: bool = True  # owners who don't plan weekly set this to False
    active: bool = True


@dataclass(frozen=True)
class TeamSpec:
    name: str
    description: str
    lead: str
    members: tuple[str, ...]
    library: tuple[Content, ...]


@dataclass(frozen=True)
class OrgSpec:
    name: str
    domain: str
    people: tuple[Person, ...]
    teams: tuple[TeamSpec, ...]
    suspended_reason: str | None = None


@dataclass
class Week:
    """How one member's week went, for the scenario tables below."""

    status: PlanStatus
    ticked: int = 0  # tasks ticked off, beyond the main task
    shipped: bool | None = None
    note: str | None = None
    returned_with: str | None = None
    content: Content | None = None  # override the library pick


# --- Plan content --------------------------------------------------------------------------

PAYMENTS = (
    Content(
        "Expired cards are retried automatically at renewal, verified on staging",
        "Expired cards are the top cause of failed renewals; recovering them "
        "keeps revenue without a support ticket.",
        (
            "Card updater webhook stores new expiry dates",
            "Retry schedule covered by integration tests in CI",
            "Failed-retry email uses the new template",
        ),
        (
            "Changelog entry for automatic card updates",
            "checkout_retry_succeeded event tracked in analytics",
        ),
    ),
    Content(
        "EU customers can pay invoices by bank transfer, live for 10% of workspaces",
        "EU customers keep asking for SEPA; card-only checkout loses our largest "
        "invoices.",
        (
            "SEPA mandate flow passes the provider's test suite",
            "Transfer status shows on the invoice page",
            "Reconciliation job matches incoming transfers",
        ),
        (
            "sepa_transfers flag rolled out to 10% of EU workspaces",
            "Help center article on paying by bank transfer",
        ),
    ),
    Content(
        "Refunds from the dashboard reach the ledger within a minute in production",
        "Support issues refunds by hand today; self-serve refunds clear that queue.",
        (
            "Partial refunds supported in the refund dialog",
            "Nightly ledger report reconciles refunds",
        ),
        ("Refunds walkthrough added to the onboarding checklist",),
    ),
    Content(
        "EU business customers can add a VAT ID at checkout, live behind a flag",
        "Without a VAT ID, EU businesses can't reclaim tax and churn to competitors.",
        (
            "VAT ID validated against VIES before saving",
            "Invoices show the reverse-charge note when a VAT ID is present",
            "Existing customers can add a VAT ID from billing settings",
        ),
        ("vat_id_checkout flag on for internal workspaces",),
    ),
    Content(
        "Dunning emails stop the moment a payment succeeds, verified on staging",
        "Customers who already paid still get chased, and they tell us about it.",
        (
            "Payment success cancels queued dunning jobs",
            "Regression test for the paid-then-dunned case",
        ),
        ("Support macro updated for the dunning fix",),
    ),
)

PLATFORM = (
    Content(
        "Postgres 16 upgrade completed on staging with zero failed jobs over 24h",
        "Postgres 13 leaves support in November; upgrading on our schedule beats "
        "upgrading in a hurry.",
        (
            "Upgrade runbook rehearsed on a production snapshot",
            "Extensions verified compatible",
            "Rollback tested and timed",
        ),
        ("Maintenance window announced in #eng-announcements",),
    ),
    Content(
        "Background jobs survive a worker restart without loss, proven by a chaos test",
        "Lost jobs mean missed invoices; customers notice before we do.",
        (
            "Jobs acknowledged only after completion",
            "Chaos test kills a worker mid-batch in CI",
        ),
        ("Incident review doc updated with the fix",),
    ),
    Content(
        "Main CI pipeline finishes in under 10 minutes, measured over 20 runs",
        "Slow CI is the biggest drag on how often we ship.",
        (
            "Test suite split across four parallel runners",
            "Docker layer cache shared between jobs",
            "Flaky checkout test fixed or quarantined",
        ),
        ("CI timing chart shared in #engineering",),
    ),
    Content(
        "Public API returns 429 with Retry-After under load, live in production",
        "One noisy integration took the API down last month; limits protect "
        "everyone else.",
        (
            "Per-key limits configurable without a deploy",
            "Load test confirms limits hold at 5x normal traffic",
        ),
        (
            "API docs explain the limits and headers",
            "Email to integrators about the new limits",
        ),
    ),
    Content(
        "Feature flags support percentage rollouts, used by the SEPA launch",
        "Payments needs gradual rollouts to ship risky changes safely.",
        (
            "Rollout percentage editable in the flag admin",
            "Sticky bucketing per workspace",
        ),
        ("How-to on percentage rollouts in the eng handbook",),
    ),
)

LEADS = (
    Content(
        "Q4 payments roadmap agreed with product and posted in #payments",
        "The team needs one list of what we're shipping this quarter.",
        ("Draft reviewed with each engineer", "Dependencies on Platform listed"),
        ("Roadmap summary shared in the all-hands doc",),
    ),
    Content(
        "On-call runbook covers the top five alerts, reviewed by the team",
        "New on-call engineers spend their first night guessing.",
        ("Each alert has a first-five-minutes checklist", "Runbook linked from alerts"),
        ("Runbook walkthrough recorded for new hires",),
    ),
    Content(
        "Hiring loop for the senior payments role finalized and posted",
        "We're a person short and the backlog shows it.",
        (
            "Take-home replaced with a pairing session",
            "Scorecard agreed with recruiting",
        ),
        ("Job post shared on the careers page",),
    ),
)

PATIENT_APP = (
    Content(
        "Patients can reschedule appointments in the app, live for iOS beta testers",
        "Rescheduling by phone is the clinics' most common front-desk call.",
        (
            "Reschedule screen shows the clinic's open slots",
            "Clinic calendar updates within a minute",
            "Edge case: same-day reschedules blocked with a clear message",
        ),
        (
            "TestFlight release notes mention rescheduling",
            "appointment_rescheduled event tracked",
        ),
    ),
    Content(
        "Appointment reminders go out 24 hours ahead, verified on TestFlight",
        "No-shows cost clinics a full slot; reminders are the cheapest fix.",
        (
            "Reminder respects the patient's time zone",
            "Patients can turn reminders off in settings",
        ),
        ("Clinic newsletter blurb about reminders",),
    ),
    Content(
        "Android home screen loads in under 2 seconds on a Pixel 6, measured in CI",
        "Slow startup is the top complaint in Play Store reviews.",
        ("Startup trace captured in CI", "Images lazy-loaded below the fold"),
        ("Play Store release notes call out the faster start",),
    ),
    Content(
        "Every booking screen passes a VoiceOver audit",
        "Two clinics serve patients with low vision and have asked for this.",
        ("Buttons have accessible labels", "Dynamic type supported on booking flow"),
        ("Accessibility statement updated on the website",),
    ),
)

CLINICAL_DATA = (
    Content(
        "Lab results import from the HL7 feed with zero dropped messages over 24h",
        "Missing lab results put clinicians at risk of acting on stale data.",
        (
            "Parser handles the three message variants we receive",
            "Dead-letter queue alerts after 5 failures",
        ),
        ("Clinic admins notified that lab sync is live",),
    ),
    Content(
        "Audit log records every chart view, exported for the compliance review",
        "The compliance review in two weeks needs a complete access trail.",
        ("Chart views logged with user and timestamp", "Export matches spot checks"),
        ("Compliance lead walked through the export",),
    ),
    Content(
        "Retention job deletes expired records nightly, verified with a dry-run report",
        "Keeping records past retention is a legal liability.",
        ("Dry-run mode lists what would be deleted", "Deletions logged for audit"),
        ("Retention policy page updated for clinics",),
    ),
)

STUDIO = (
    Content(
        "Client portal shows project status updates, live for two pilot clients",
        "Clients email for status every week; the portal answers before they ask.",
        ("Status updates editable by project leads",),
        ("Pilot clients emailed a walkthrough",),
    ),
)

# A plan the AI reviewer should take apart: activities instead of results, no
# why, no go-to-market, and checkout work that didn't ship last week either.
VAGUE_DRAFT = Content(
    "Implement checkout",
    None,
    ("Write tests", "Fix the webhook bug", "Look into the slow invoice page"),
)

# --- Organizations ------------------------------------------------------------------------

NORTHWIND = OrgSpec(
    name="Northwind Labs",
    domain="northwind.example",
    people=(
        Person("priya", "Priya", "Raman", "owner", plans=False),
        Person("jordan", "Jordan", "Blake", "admin"),
        Person("marcus", "Marcus", "Chen", "member"),
        Person("sofia", "Sofia", "Alvarez", "member"),
        Person("aisha", "Aisha", "Bello", "member"),
        Person("tom", "Tom", "Novak", "member"),
        Person("lena", "Lena", "Fischer", "member"),
        Person("ken", "Ken", "Ito", "member"),
        Person("dev", "Dev", "Patel", "member"),
        Person("ben", "Ben", "Carter", "member", plans=False, active=False),
    ),
    teams=(
        TeamSpec(
            "Payments",
            "Checkout, billing and payouts.",
            lead="marcus",
            members=("marcus", "aisha", "tom", "lena"),
            library=PAYMENTS,
        ),
        TeamSpec(
            "Platform",
            "Infrastructure, CI and the developer platform.",
            lead="sofia",
            members=("sofia", "ken", "dev", "tom", "jordan"),
            library=PLATFORM,
        ),
        TeamSpec(
            "Engineering Leads",
            "Team leads; their plans are reviewed by the CTO.",
            lead="priya",
            members=("priya", "marcus", "sofia"),
            library=LEADS,
        ),
    ),
)

LUMEN = OrgSpec(
    name="Lumen Health",
    domain="lumen.example",
    people=(
        Person("elena", "Elena", "Rossi", "owner", plans=False),
        Person("omar", "Omar", "Haddad", "admin"),
        Person("noah", "Noah", "Kim", "member"),
        Person("grace", "Grace", "Mensah", "member"),
        Person("hana", "Hana", "Sato", "member"),
    ),
    teams=(
        TeamSpec(
            "Patient App",
            "The iOS and Android apps patients use.",
            lead="noah",
            members=("noah", "grace", "omar"),
            library=PATIENT_APP,
        ),
        TeamSpec(
            "Clinical Data",
            "Integrations with clinic systems.",
            lead="elena",
            members=("elena", "hana", "noah"),
            library=CLINICAL_DATA,
        ),
    ),
)

BRIGHTLINE = OrgSpec(
    name="Brightline Studio",
    domain="brightline.example",
    people=(
        Person("kai", "Kai", "Larsen", "owner", plans=False),
        Person("mia", "Mia", "Torres", "member"),
    ),
    teams=(
        TeamSpec(
            "Studio",
            "Client work.",
            lead="kai",
            members=("kai", "mia"),
            library=STUDIO,
        ),
    ),
    suspended_reason="Chargeback dispute on the last invoice; reinstate once resolved.",
)

# This week's state of play, by person. Older weeks are generated.
THIS_WEEK: dict[str, Week] = {
    "aisha": Week("submitted"),
    "tom": Week("approved", ticked=2),
    "lena": Week("draft", content=VAGUE_DRAFT),
    "marcus": Week("submitted"),
    "sofia": Week("approved", ticked=1),
    "ken": Week(
        "draft",
        returned_with="This is three projects. Pick the Postgres upgrade, make it the "
        "main task and move the rest to next week.",
        content=Content(
            "Upgrade Postgres, move CI to the new runners and add API rate limits",
            "Platform debt is slowing every team down.",
            ("Postgres upgrade", "New CI runners", "Rate limiting"),
        ),
    ),
    "jordan": Week("approved", ticked=2),
    # dev hasn't started a plan yet
    "omar": Week("approved", ticked=1),
    "noah": Week("submitted"),
    "grace": Week("submitted"),
    "hana": Week("approved", ticked=2),
}

LAST_WEEK: dict[str, Week] = {
    "tom": Week(
        "done",
        ticked=1,
        shipped=False,
        note="Blocked by the card network's sandbox outage on Wednesday; the "
        "retries pick up again once it's back.",
        content=Content(
            "Declined renewals retry automatically, verified against the card "
            "network's sandbox",
            "A declined renewal cancels the subscription today, even when the "
            "card would work a day later.",
            (
                "Retry schedule stored per subscription",
                "Retries stop as soon as a payment succeeds",
            ),
            ("Changelog entry for automatic renewal retries",),
        ),
    ),
    "lena": Week(
        "done",
        ticked=1,
        shipped=False,
        note="Checkout refactor took longer than planned.",
        content=Content(
            "Checkout handles expired cards, confirmed on staging",
            "Expired cards fail renewals silently.",
            ("Card form shows the expiry error", "Webhook retries don't drop events"),
            ("Changelog entry for the checkout fix",),
        ),
    ),
    "ken": Week("approved", ticked=2),  # never closed out
    "grace": Week(
        "done", ticked=1, shipped=False, note="Waiting on clinic API access."
    ),
}


@dataclass
class SeedReport:
    logins: list[tuple[str, str]] = field(default_factory=list)
    invite_path: str = f"/join/{DEMO_INVITE_TOKEN}"
    organizations: int = 0
    users: int = 0
    plans: int = 0


class DemoSeeder:
    def __init__(self, session: AsyncSession, *, week_start: date | None = None):
        self.session = session
        self.now = utcnow()
        self.this_week = week_start or current_week_start()
        self.random = random.Random(2026)
        self.report = SeedReport()

    async def run(self) -> SeedReport:
        staff = self._user("Riley", "Morgan", "staff@planstride.example", staff=True)
        self.report.logins.append(("Platform staff (internal console)", staff.email))

        orgs: dict[str, tuple[Organization, dict[str, User]]] = {}
        for spec in (NORTHWIND, LUMEN, BRIGHTLINE):
            orgs[spec.name] = await self._organization(spec)

        northwind, people = orgs[NORTHWIND.name]
        self.report.logins += [
            ("Org owner (Northwind Labs)", people["priya"].email),
            ("Org admin, not a lead", people["jordan"].email),
            ("Team lead (Payments)", people["marcus"].email),
            ("Member (Payments)", people["aisha"].email),
            ("Member with a vague draft", people["lena"].email),
            ("Member on two teams", people["tom"].email),
            ("Owner of another org (Lumen Health)", orgs[LUMEN.name][1]["elena"].email),
            ("Member of a suspended org", orgs[BRIGHTLINE.name][1]["mia"].email),
        ]
        self.session.add(
            Invitation(
                organization_id=northwind.id,
                created_by_id=people["priya"].id,
                role="member",
                token_hash=hash_invite_token(DEMO_INVITE_TOKEN),
                expires_at=self.now + INVITATION_TTL,
            )
        )
        self._ai_usage(list(orgs.values()))
        await self.session.flush()
        return self.report

    # --- Builders -------------------------------------------------------------------------

    def _user(
        self,
        first: str,
        last: str,
        email: str,
        *,
        staff: bool = False,
        active: bool = True,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            first_name=first,
            last_name=last,
            email=email,
            password=hash_password(DEMO_PASSWORD),
            is_active=active,
            is_platform_staff=staff,
            created_at=self._at(self.this_week - timedelta(weeks=10), hour=10),
            last_login_at=self.now
            - (
                timedelta(minutes=self.random.randint(20, 60 * 72))
                if active
                else timedelta(days=40)
            ),
        )
        self.session.add(user)
        self.report.users += 1
        return user

    async def _organization(
        self, spec: OrgSpec
    ) -> tuple[Organization, dict[str, User]]:
        organization = Organization(
            id=uuid.uuid4(),
            name=spec.name,
            created_at=self._at(self.this_week - timedelta(weeks=9), hour=11),
        )
        if spec.suspended_reason:
            organization.suspended_at = self.now - timedelta(days=2)
            organization.suspension_reason = spec.suspended_reason
        self.session.add(organization)
        self.report.organizations += 1

        people: dict[str, User] = {}
        for person in spec.people:
            user = self._user(
                person.first_name,
                person.last_name,
                f"{person.key}@{spec.domain}",
                active=person.active,
            )
            people[person.key] = user
            self.session.add(
                Membership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role=person.role,
                    created_at=organization.created_at + timedelta(days=1),
                )
            )
        await self.session.flush()

        library_of: dict[str, tuple[Content, ...]] = {}
        for team_spec in spec.teams:
            team = Team(
                id=uuid.uuid4(),
                organization_id=organization.id,
                name=team_spec.name,
                description=team_spec.description,
                lead_user_id=people[team_spec.lead].id,
            )
            self.session.add(team)
            await self.session.flush()
            for key in team_spec.members:
                self.session.add(
                    TeamMembership(
                        organization_id=organization.id,
                        team_id=team.id,
                        user_id=people[key].id,
                    )
                )
                # A member's plans draw on the work of every team they're on.
                library_of[key] = library_of.get(key, ()) + team_spec.library

        reviewers = _reviewers(spec)
        for index, person in enumerate(spec.people):
            if not person.plans or person.key not in library_of:
                continue
            reviewer = (
                people[reviewers[person.key]] if person.key in reviewers else None
            )
            for offset in range(WEEKS_OF_HISTORY):
                week = self._week_for(person.key, offset)
                if week is None:
                    continue
                library = library_of[person.key]
                content = week.content or library[(index + offset) % len(library)]
                self._plan(
                    organization,
                    people[person.key],
                    self.this_week - timedelta(weeks=offset),
                    content,
                    week,
                    reviewer,
                )
        await self.session.flush()
        return organization, people

    def _week_for(self, key: str, offset: int) -> Week | None:
        if offset == 0:
            return THIS_WEEK.get(key)
        if offset == 1 and key in LAST_WEEK:
            return LAST_WEEK[key]
        roll = self.random.random()
        if roll < 0.08:
            return None  # skipped a week
        if roll < 0.28:
            return Week("done", ticked=1, shipped=False, note="Ran out of week.")
        return Week("done", ticked=3, shipped=True)

    def _plan(
        self,
        organization: Organization,
        author: User,
        week_start: date,
        content: Content,
        week: Week,
        reviewer: User | None,
    ) -> None:
        tasks = [PlanTask(kind="main", title=content.main, position=0)]
        kinds: list[tuple[TaskKind, Sequence[str]]] = [
            ("sub_goal", content.sub_goals),
            ("go_to_market", content.go_to_market),
        ]
        for kind, titles in kinds:
            for title in titles:
                tasks.append(PlanTask(kind=kind, title=title, position=len(tasks)))

        created = self._at(week_start, hour=9)
        for task in tasks:
            task.created_at = created
        plan = WeeklyPlan(
            organization_id=organization.id,
            user_id=author.id,
            week_start=week_start,
            status=week.status,
            why_it_matters=content.why,
            tasks=tasks,
            created_at=created,
        )
        if week.status != "draft":
            plan.submitted_at = self._at(week_start, hour=10)
        if week.status in ("approved", "done") and reviewer is not None:
            plan.reviewed_by_id = reviewer.id
            plan.reviewed_at = self._at(week_start, hour=14)
            plan.review_decision = "approved"
        if week.returned_with and reviewer is not None:
            plan.reviewed_by_id = reviewer.id
            plan.reviewed_at = self._at(week_start, hour=15)
            plan.review_decision = "returned"
            plan.review_comment = week.returned_with
        if week.status == "done":
            plan.completed_at = self._at(week_start + timedelta(days=4), hour=17)
            plan.main_task_shipped = week.shipped
            plan.outcome_note = week.note

        # Tick tasks: sub-goals and go-to-market first, the main task if shipped.
        others = [task for task in tasks if task.kind != "main"]
        for task in others[: week.ticked]:
            task.status = "done"
            task.completed_at = self._at(week_start + timedelta(days=2), hour=16)
        if week.shipped:
            tasks[0].status = "done"
            tasks[0].completed_at = plan.completed_at
        self.session.add(plan)
        self.report.plans += 1

    def _ai_usage(self, orgs: list[tuple[Organization, dict[str, User]]]) -> None:
        volumes = {NORTHWIND.name: 70, LUMEN.name: 30, BRIGHTLINE.name: 4}
        for organization, people in orgs:
            members = [user for user in people.values() if user.is_active]
            latest = organization.suspended_at or self.now
            for _ in range(volumes[organization.name]):
                feature: AIFeature = (
                    "plan_review" if self.random.random() < 0.7 else "plan_draft"
                )
                roll = self.random.random()
                outcome: AIOutcome = "success"
                error_type: AIErrorType | None = None
                if roll > 0.93:
                    outcome, error_type = "rate_limited", "provider_rate_limit"
                elif roll > 0.89:
                    outcome = "failed"
                    error_type = self.random.choice(
                        ("timeout", "invalid_output", "provider_error")
                    )
                succeeded = outcome == "success"
                base_input = 1350 if feature == "plan_review" else 700
                self.session.add(
                    AIUsageEvent(
                        organization_id=organization.id,
                        user_id=self.random.choice(members).id,
                        feature=feature,
                        outcome=outcome,
                        error_type=error_type,
                        model_name="gemini-3.5-flash-lite",
                        latency_ms=(
                            self.random.randint(25_000, 26_000)
                            if error_type == "timeout"
                            else self.random.randint(700, 3800)
                        ),
                        input_tokens=base_input + self.random.randint(0, 600)
                        if succeeded
                        else None,
                        output_tokens=self.random.randint(180, 520)
                        if succeeded
                        else None,
                        created_at=latest
                        - timedelta(minutes=self.random.randint(5, 60 * 24 * 26)),
                    )
                )

    def _at(self, day: date, *, hour: int) -> datetime:
        """A timestamp on `day`, never later than now (this week is still live)."""
        moment = datetime.combine(day, time(hour=hour), tzinfo=UTC)
        return min(moment, self.now - timedelta(minutes=30))


def _reviewers(spec: OrgSpec) -> dict[str, str]:
    """Who approves each member's plans: the lead of their first team led by
    someone else."""
    reviewers: dict[str, str] = {}
    for team in spec.teams:
        for key in team.members:
            if key != team.lead:
                reviewers.setdefault(key, team.lead)
    return reviewers


async def has_data(session: AsyncSession) -> bool:
    return bool(await session.scalar(text("SELECT EXISTS (SELECT 1 FROM users)")))


async def wipe(session: AsyncSession) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
