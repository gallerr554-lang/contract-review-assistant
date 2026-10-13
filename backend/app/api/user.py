from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import AdminUser
from app.database.session import get_db
from app.schemas.user_management import (
    ManagedUserListResponse,
    ManagedUserResponse,
    UserPasswordResetRequest,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.service.user_management_service import (
    ManagedUserConflictError,
    ManagedUserNotFoundError,
    UserManagementService,
)

router = APIRouter()
user_management_service = UserManagementService()


def user_response(user, task_count: int) -> ManagedUserResponse:
    return ManagedUserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        create_time=user.create_time,
        last_login_time=user.last_login_time,
        task_count=task_count,
    )


@router.get("", response_model=ManagedUserListResponse)
def list_users(
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    role: Literal["user", "admin"] | None = None,
    enabled: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> ManagedUserListResponse:
    del admin
    items, total = user_management_service.list_users(
        db, keyword, role, enabled, page, page_size
    )
    return ManagedUserListResponse(
        items=[user_response(user, task_count) for user, task_count in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=ManagedUserResponse)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ManagedUserResponse:
    del admin
    try:
        return user_response(*user_management_service.get_user_with_task_count(db, user_id))
    except ManagedUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{user_id}/status", response_model=ManagedUserResponse)
def update_user_status(
    user_id: int,
    request: UserStatusUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ManagedUserResponse:
    try:
        return user_response(
            *user_management_service.set_status(db, admin.id, user_id, request.status)
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManagedUserConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{user_id}/role", response_model=ManagedUserResponse)
def update_user_role(
    user_id: int,
    request: UserRoleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ManagedUserResponse:
    try:
        return user_response(
            *user_management_service.set_role(db, admin.id, user_id, request.role)
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManagedUserConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{user_id}/reset-password", response_model=ManagedUserResponse)
def reset_user_password(
    user_id: int,
    request: UserPasswordResetRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ManagedUserResponse:
    try:
        return user_response(
            *user_management_service.reset_password(
                db, admin.id, user_id, request.new_password
            )
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManagedUserConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
