from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RuleType = Literal["AI语义审查", "条款完整性", "合规校验", "金额与支付"]
RiskLevel = Literal["high", "medium", "low"]


class StatusUpdate(BaseModel):
    status: bool


class RuleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rule_name: str = Field(min_length=1, max_length=40)
    business_type: Literal["合同审查"] = "合同审查"
    rule_type: RuleType
    risk_level: RiskLevel
    review_requirement: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=500)
    status: bool = True


class RuleUpdateRequest(RuleCreateRequest):
    pass


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: str
    rule_name: str
    business_type: str
    rule_type: str
    risk_level: str
    review_requirement: str
    description: str | None
    status: bool
    update_time: datetime


class RuleSummary(BaseModel):
    id: int
    rule_id: str
    rule_name: str
    rule_type: str
    risk_level: str
    status: bool


class SceneCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scene_name: str = Field(min_length=1, max_length=40)
    business_type: Literal["合同审查"] = "合同审查"
    description: str | None = Field(default=None, max_length=200)
    system_prompt: str = Field(min_length=1, max_length=4000)
    rule_ids: list[int] = Field(min_length=1)
    status: bool = True
    display_order: int = Field(default=1, ge=1, le=99)


class SceneUpdateRequest(SceneCreateRequest):
    pass


class SceneResponse(BaseModel):
    id: int
    scene_name: str
    business_type: str
    description: str | None
    system_prompt: str
    status: bool
    display_order: int
    update_time: datetime
    rules: list[RuleSummary]
    rule_count: int
    active_rule_count: int


class AvailableSceneResponse(BaseModel):
    id: int
    scene_name: str
    description: str | None
