from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import require_admin
from app.schemas.configuration import (
    RiskLevel,
    RuleCreateRequest,
    RuleResponse,
    RuleType,
    RuleUpdateRequest,
    StatusUpdate,
)
from app.service.rule_service import RuleNotFoundError, RuleService

router = APIRouter(dependencies=[Depends(require_admin)])
rule_service = RuleService()


@router.get("", response_model=list[RuleResponse])
def list_rules(
    db: Annotated[Session, Depends(get_db)],
    keyword: Annotated[str | None, Query(max_length=80)] = None,
    rule_type: RuleType | None = None,
    risk_level: RiskLevel | None = None,
    enabled: bool | None = None,
) -> list[RuleResponse]:
    return [
        RuleResponse.model_validate(rule)
        for rule in rule_service.list_rules(db, keyword, rule_type, risk_level, enabled)
    ]


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    request: RuleCreateRequest, db: Annotated[Session, Depends(get_db)]
) -> RuleResponse:
    return RuleResponse.model_validate(rule_service.create_rule(db, request))


@router.put("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: int,
    request: RuleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(rule_service.update_rule(db, rule_id, request))
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{rule_id}/status", response_model=RuleResponse)
def update_rule_status(
    rule_id: int,
    request: StatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            rule_service.set_status(db, rule_id, request.status)
        )
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Annotated[Session, Depends(get_db)]) -> Response:
    try:
        rule_service.delete_rule(db, rule_id)
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
