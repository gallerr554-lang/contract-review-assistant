from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Scale = Literal["宽松", "标准", "严格"]
Position = Literal["甲方", "乙方"]


class ReviewCreateRequest(BaseModel):
    upload_id: str = Field(min_length=36, max_length=36)
    scene_id: int = Field(gt=0)
    scale: Scale = "标准"
    position: Position = "甲方"


class ReviewTaskResponse(BaseModel):
    id: int
    task_no: str
    contract_name: str
    scene_name: str
    scale: str
    position: str
    status: str
    progress: int
    current_step: int
    current_message: str
    error_message: str | None
    create_time: datetime


class RiskLocationSpan(BaseModel):
    source_file_id: str
    page_number: int
    block_id: str
    start_offset: int
    end_offset: int
    anchor_text: str
    anchor_hash: str


class ReviewRiskResponse(BaseModel):
    id: int
    risk_name: str
    risk_level: str
    rule_id: str
    rule_name: str
    original_text: str | None
    source: str | None
    locatable: bool
    description: str
    suggestion: str
    feedback_submitted: bool = False
    page_number: int | None = None
    source_file_id: str | None = None
    block_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    anchor_text: str | None = None
    anchor_hash: str | None = None
    location_spans: list[RiskLocationSpan] = Field(default_factory=list)


class RiskStatistics(BaseModel):
    total: int
    high: int
    medium: int
    low: int


class ReviewResultResponse(BaseModel):
    task: ReviewTaskResponse
    summary: str
    document: "DocumentMetaResponse"
    documents: list["DocumentMetaResponse"] = Field(default_factory=list)
    statistics: RiskStatistics
    risks: list[ReviewRiskResponse]


class DocumentMetaResponse(BaseModel):
    file_id: str = "main"
    file_name: str
    file_extension: str
    mime_type: str
    page_count: int
    ocr_used: bool = False
    ocr_status: str = "not_required"
    ocr_message: str | None = None
    text_source: str = "native"
    preview_available: bool = False


class DocumentPageResponse(BaseModel):
    file_id: str = "main"
    page_number: int
    page_count: int
    text: str
    blocks: list[dict]
    ocr_used: bool = False
    text_source: str = "native"
    risk_ids: list[int] = Field(default_factory=list)


class ReviewHistoryItem(BaseModel):
    id: int
    task_no: str
    contract_name: str
    scene_name: str
    scale: str
    position: str
    status: str
    risk_total: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    error_message: str | None
    create_time: datetime


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryItem]
    total: int
    page: int
    page_size: int


class RiskFeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=500)


class RiskFeedbackResponse(BaseModel):
    id: int
    task_id: int
    risk_id: int
    rule_id: str
    content: str
    create_time: datetime


class ModelRisk(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    level: Literal["high", "medium", "low"]
    rule_id: str = Field(min_length=1, max_length=64)
    rule_name: str = Field(min_length=1, max_length=100)
    original_text: str | None = None
    source: str | None = None
    source_file_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    context_before: str | None = Field(default=None, max_length=500)
    context_after: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class ModelReviewOutput(BaseModel):
    summary: str = Field(min_length=1)
    risks: list[ModelRisk] = Field(default_factory=list)
