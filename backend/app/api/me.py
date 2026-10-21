from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import AuthUser, current_user

router = APIRouter()


@router.get("/me")
def me(user: Annotated[AuthUser, Depends(current_user)]) -> AuthUser:
    return user
