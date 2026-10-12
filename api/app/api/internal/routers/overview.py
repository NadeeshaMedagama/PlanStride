from fastapi import APIRouter

from app.api.internal.access import CurrentInternalUser
from app.api.internal.schemas import OverviewResponse
from app.database import DBSession
from app.services.backoffice import BackofficeService

router = APIRouter()


@router.get("/overview", tags=["overview"])
async def overview_get(
    current_user: CurrentInternalUser, session: DBSession
) -> OverviewResponse:
    """Headline numbers for the staff dashboard."""
    overview = await BackofficeService(session).overview()
    return OverviewResponse.model_validate(overview)
