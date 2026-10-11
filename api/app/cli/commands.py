import asyncio
import inspect
import secrets
from functools import partial, wraps

from pydantic import ValidationError
from sqlalchemy import select
from typer import BadParameter, Exit, Option, Typer, echo

from app.cli.schemas import UserCreate
from app.cli.seed import DEMO_PASSWORD, DemoSeeder, has_data, wipe
from app.config import settings
from app.database import AsyncSessionLocal, async_engine
from app.models import User
from app.security import hash_password


class AsyncTyper(Typer):
    @staticmethod
    def maybe_run_async(decorator, f):
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            def runner(*args, **kwargs):
                # Close the shared session and dispose the engine's pool inside
                # the same event loop asyncio.run creates, so pooled asyncpg
                # connections are returned before the loop's greenlet is
                # finalized (otherwise the GC terminates them post-loop and
                # SQLAlchemy warns about non-checked-in connections).
                async def main():
                    try:
                        return await f(*args, **kwargs)
                    finally:
                        await session.close()
                        await async_engine.dispose()

                return asyncio.run(main())

            decorator(runner)
        else:
            decorator(f)
        return f

    def callback(self, *args, **kwargs):
        decorator = super().callback(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)

    def command(self, *args, **kwargs):
        decorator = super().command(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)


session = AsyncSessionLocal()
cli = AsyncTyper()


@cli.callback()
def main():
    """PlanStride management CLI."""
    # Present so Typer always runs in subcommand mode (`manage.py create-user`),
    # even while there is only a single command registered.


@cli.command()
async def create_user(
    first_name: str = Option(...),
    last_name: str = Option(...),
    email: str = Option(...),
    password: str = Option(None, help="Login password. Generated if not given."),
    admin: bool = Option(
        False,
        "--admin",
        help="Make this user PlanStride platform staff (internal console access). "
        "This is not an organization role.",
    ),
):
    """Create a user.

    The login password is generated unless provided with --password. Pass
    --admin to create platform staff; this is the only way staff accounts are
    made (never through sign-up or the console).
    """
    try:
        data = UserCreate(first_name=first_name, last_name=last_name, email=email)
    except ValidationError as e:
        raise BadParameter("; ".join(err["msg"] for err in e.errors()))

    existing = (
        (await session.execute(select(User).where(User.email == data.email)))
        .scalars()
        .first()
    )
    if existing:
        raise BadParameter(f"User with email '{data.email}' already exists.")

    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    user = User(
        **data.model_dump(),
        password=hash_password(password),
        is_active=True,
        is_platform_staff=admin,
    )
    session.add(user)
    await session.commit()
    print(f"{'Platform staff' if admin else 'User'} created: ", user.id)
    if generated:
        print("Generated password: ", password)


@cli.command()
async def seed(
    reset: bool = Option(
        False,
        "--reset",
        help="Wipe every table first. Development only.",
    ),
):
    """Load the demo: three organizations, teams, members in every role and six
    weeks of plans dated relative to today."""
    if settings.is_production:
        echo("Refusing to seed a production database.", err=True)
        raise Exit(code=1)
    if await has_data(session):
        if not reset:
            echo(
                "The database already has data. Re-run with --reset to wipe it "
                "and load the demo again.",
                err=True,
            )
            raise Exit(code=1)
        await wipe(session)

    report = await DemoSeeder(session).run()
    await session.commit()

    echo(
        f"Seeded {report.organizations} organizations, {report.users} users "
        f"and {report.plans} plans.\n"
    )
    echo(f"Every demo account uses the password: {DEMO_PASSWORD}\n")
    width = max(len(label) for label, _ in report.logins)
    for label, email in report.logins:
        echo(f"  {label.ljust(width)}  {email}")
    echo(
        f"\nInvite link into Northwind Labs: http://localhost:3001{report.invite_path}"
    )
