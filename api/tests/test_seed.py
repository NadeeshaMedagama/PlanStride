from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.cli.seed import DEMO_INVITE_TOKEN, DemoSeeder, has_data, wipe
from app.domain import current_week_start
from app.models import Organization, User, WeeklyPlan
from app.services.organizations import OrganizationService
from app.services.plans import PlanService


async def test_seed_builds_a_demo_that_follows_the_products_rules(db):
    report = await DemoSeeder(db).run()
    await db.commit()

    assert report.organizations == 3
    assert {label for label, _ in report.logins} >= {
        "Platform staff (internal console)",
        "Org owner (Northwind Labs)",
        "Team lead (Payments)",
        "Member (Payments)",
    }

    staff = await db.scalar(select(User).where(User.is_platform_staff.is_(True)))
    assert staff is not None and staff.email == "staff@planstride.example"
    suspended = await db.scalar(
        select(Organization).where(Organization.suspended_at.is_not(None))
    )
    assert suspended is not None and suspended.name == "Brightline Studio"
    assert await db.scalar(select(User).where(User.is_active.is_(False))) is not None

    plans = (
        await db.scalars(select(WeeklyPlan).options(selectinload(WeeklyPlan.tasks)))
    ).all()
    assert all(plan.week_start.weekday() == 0 for plan in plans)
    assert all(sum(t.kind == "main" for t in plan.tasks) == 1 for plan in plans)
    this_week = {
        plan.status for plan in plans if plan.week_start == current_week_start()
    }
    assert {"draft", "submitted", "approved"} <= this_week

    # Every seeded approval was made by someone the reviewer rule allows.
    service = PlanService(db)
    for plan in plans:
        if plan.reviewed_by_id is not None:
            assert await service.can_review(
                plan.organization_id, plan.reviewed_by_id, plan.user_id
            ), plan.id

    invitation = await OrganizationService(db).get_valid_invitation(DEMO_INVITE_TOKEN)
    assert invitation.organization.name == "Northwind Labs"


async def test_seed_can_be_wiped_and_repeated(db):
    await DemoSeeder(db).run()
    await db.commit()
    assert await has_data(db)

    await wipe(db)
    await DemoSeeder(db).run()
    await db.commit()
    assert await db.scalar(select(func.count()).select_from(Organization)) == 3
