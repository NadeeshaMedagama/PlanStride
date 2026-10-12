from fastapi import (
    APIRouter,
)

from app.api.app.access import CurrentUser
from app.api.app.schemas import UserResponse

router = APIRouter()


@router.get("/users/self", tags=["users"])
async def get_current_user(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
