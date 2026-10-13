from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import AdminUser, CurrentUser
from app.models.rule import ReviewRule
from app.models.scene import ReviewScene
from app.schemas.configuration import (
    AvailableSceneResponse,
    RuleSummary,
    SceneCreateRequest,
    SceneResponse,
    SceneUpdateRequest,
    StatusUpdate,
)
from app.service.scene_service import SceneNotFoundError, SceneService, SceneValidationError

router = APIRouter()
scene_service = SceneService()


def scene_response(scene: ReviewScene, rules: list[ReviewRule]) -> SceneResponse:
    summaries = [RuleSummary.model_validate(rule, from_attributes=True) for rule in rules]
    return SceneResponse(
        id=scene.id,
        scene_name=scene.scene_name,
        business_type=scene.business_type,
        description=scene.description,
        system_prompt=scene.system_prompt,
        status=scene.status,
        display_order=scene.display_order,
        update_time=scene.update_time,
        rules=summaries,
        rule_count=len(rules),
        active_rule_count=sum(1 for rule in rules if rule.status),
    )


@router.get("/available", response_model=list[AvailableSceneResponse])
def list_available_scenes(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> list[AvailableSceneResponse]:
    del user
    return [
        AvailableSceneResponse.model_validate(scene, from_attributes=True)
        for scene in scene_service.list_available(db)
    ]


@router.get("", response_model=list[SceneResponse])
def list_scenes(
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
    keyword: Annotated[str | None, Query(max_length=80)] = None,
    enabled: bool | None = None,
) -> list[SceneResponse]:
    del admin
    return [
        scene_response(scene, rules)
        for scene, rules in scene_service.list_scenes(db, keyword, enabled)
    ]


@router.post("", response_model=SceneResponse, status_code=status.HTTP_201_CREATED)
def create_scene(
    request: SceneCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> SceneResponse:
    del admin
    try:
        scene, rules = scene_service.create_scene(db, request)
        return scene_response(scene, rules)
    except SceneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{scene_id}", response_model=SceneResponse)
def update_scene(
    scene_id: int,
    request: SceneUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> SceneResponse:
    del admin
    try:
        scene, rules = scene_service.update_scene(db, scene_id, request)
        return scene_response(scene, rules)
    except SceneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SceneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{scene_id}/status", response_model=SceneResponse)
def update_scene_status(
    scene_id: int,
    request: StatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> SceneResponse:
    del admin
    try:
        scene, rules = scene_service.set_status(db, scene_id, request.status)
        return scene_response(scene, rules)
    except SceneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SceneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(
    scene_id: int, db: Annotated[Session, Depends(get_db)], admin: AdminUser
) -> Response:
    del admin
    try:
        scene_service.delete_scene(db, scene_id)
    except SceneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
