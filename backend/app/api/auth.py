from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, bearer_token
from app.database.session import get_db
from app.schemas.auth import AuthCredentials, AuthResponse, CaptchaResponse, UserResponse
from app.service.auth_service import AuthConflictError, AuthService, AuthValidationError

router = APIRouter()
auth_service = AuthService()


def auth_response(user, token: str, expires_at) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha(db: Annotated[Session, Depends(get_db)]) -> CaptchaResponse:
    captcha, image_data = auth_service.create_captcha(db)
    return CaptchaResponse(captcha_id=captcha.id, image_data=image_data, expires_at=captcha.expires_at)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: AuthCredentials, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    try:
        return auth_response(*auth_service.register(db, request))
    except AuthConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
def login(request: AuthCredentials, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    try:
        return auth_response(*auth_service.login(db, request))
    except AuthValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    del user
    auth_service.logout(db, bearer_token(authorization))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
