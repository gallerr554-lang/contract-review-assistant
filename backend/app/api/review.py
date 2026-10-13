from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import CurrentUser
from app.models.review import ReviewRisk, ReviewRiskFeedback, ReviewTask
from app.schemas.review import (
    ReviewCreateRequest,
    ReviewHistoryResponse,
    DocumentMetaResponse,
    DocumentPageResponse,
    ReviewResultResponse,
    ReviewRiskResponse,
    ReviewTaskResponse,
    RiskStatistics,
    RiskFeedbackCreateRequest,
    RiskFeedbackResponse,
)
from app.service.file_service import FileParseError
from app.service.document_service import DocumentProcessingError, DocumentService
from app.service.review_service import ReviewConfigurationError, ReviewService
from app.service.review_record_service import (
    ReviewRecordNotFoundError,
    ReviewRecordService,
    ReviewRecordValidationError,
)

router = APIRouter()
review_service = ReviewService()
record_service = ReviewRecordService()
document_service = DocumentService()


def owned_task(db: Session, task_id: int, user_id: int) -> ReviewTask:
    task = db.scalar(
        select(ReviewTask).where(ReviewTask.id == task_id, ReviewTask.user_id == user_id)
    )
    if not task:
        raise HTTPException(status_code=404, detail="审查任务不存在。")
    return task


def document_meta(task: ReviewTask, file_id: str = "main") -> DocumentMetaResponse:
    meta = document_service.document(task, file_id)
    pages = meta.get("pages", [])
    file_name = str(meta.get("file_name", task.contract_name))
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "txt"
    return DocumentMetaResponse(
        file_id=file_id,
        file_name=file_name,
        file_extension=str(meta.get("file_extension", extension)),
        mime_type=str(meta.get("mime_type", "application/octet-stream")),
        page_count=len(pages) or int(meta.get("page_count", 1)),
        ocr_used=bool(meta.get("ocr_used", False)),
        ocr_status=str(meta.get("ocr_status", "not_required")),
        ocr_message=meta.get("ocr_message"),
        text_source=str(meta.get("text_source", "native")),
        preview_available=bool(meta.get("preview_available", extension in {"pdf", "doc", "docx"})),
    )


def task_response(task: ReviewTask) -> ReviewTaskResponse:
    return ReviewTaskResponse(
        id=task.id,
        task_no=task.task_no,
        contract_name=task.contract_name,
        scene_name=task.scene_name,
        scale=task.scale,
        position=task.position,
        status=task.status,
        progress=task.progress,
        current_step=task.current_step,
        current_message=task.current_message,
        error_message=task.error_message,
        create_time=task.create_time,
    )


def prepare_document_snapshot(
    db: Session, task: ReviewTask, risks: list[ReviewRisk] | None = None
) -> None:
    changed = document_service.ensure_document_snapshot(task)
    if risks is not None:
        changed = document_service.ensure_risk_locations(task, risks) or changed
    if changed:
        db.commit()


@router.post("/create", response_model=ReviewTaskResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    request: ReviewCreateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewTaskResponse:
    if idempotency_key and len(idempotency_key) > 64:
        raise HTTPException(status_code=422, detail="幂等键长度不能超过 64 个字符。")
    try:
        task, created = review_service.create_task(db, request, user.id, idempotency_key)
    except (FileParseError, ReviewConfigurationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if created:
        background_tasks.add_task(review_service.run_review, task.id)
    return task_response(task)


@router.get("/history", response_model=ReviewHistoryResponse)
def list_review_history(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    keyword: str | None = Query(default=None, max_length=255),
    task_status: Literal["PROCESSING", "SUCCESS", "FAILED"] | None = Query(
        default=None, alias="status"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> ReviewHistoryResponse:
    items, total = record_service.list_history(
        db,
        user.id,
        keyword=keyword,
        status=task_status,
        page=page,
        page_size=page_size,
    )
    return ReviewHistoryResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{task_id}/status", response_model=ReviewTaskResponse)
def get_review_status(
    task_id: int, db: Annotated[Session, Depends(get_db)], user: CurrentUser
) -> ReviewTaskResponse:
    task = owned_task(db, task_id, user.id)
    return task_response(task)


@router.get("/{task_id}/result", response_model=ReviewResultResponse)
def get_review_result(
    task_id: int, db: Annotated[Session, Depends(get_db)], user: CurrentUser
) -> ReviewResultResponse:
    task = owned_task(db, task_id, user.id)
    if task.status != "SUCCESS":
        raise HTTPException(status_code=409, detail="审查结果尚未生成。")

    risks = list(
        db.scalars(select(ReviewRisk).where(ReviewRisk.task_id == task.id).order_by(ReviewRisk.id))
    )
    prepare_document_snapshot(db, task, risks)
    feedback_risk_ids = set(
        db.scalars(
            select(ReviewRiskFeedback.risk_id).where(
                ReviewRiskFeedback.task_id == task.id
            )
        )
    )
    counts = {
        level: sum(1 for risk in risks if risk.risk_level == level)
        for level in ("high", "medium", "low")
    }
    return ReviewResultResponse(
        task=task_response(task),
        summary=task.summary or "未识别到明显风险，建议结合业务背景进行人工复核。",
        document=document_meta(task),
        documents=[
            document_meta(task, str(item["file_id"]))
            for item in document_service.documents(task)
        ],
        statistics=RiskStatistics(total=len(risks), **counts),
        risks=[
            ReviewRiskResponse(
                **ReviewRiskResponse.model_validate(risk, from_attributes=True).model_dump(
                    exclude={"feedback_submitted"}
                ),
                feedback_submitted=risk.id in feedback_risk_ids,
            )
            for risk in risks
        ],
    )


@router.get("/{task_id}/document/pages/{page_number:int}", response_model=DocumentPageResponse)
def get_document_page(
    task_id: int,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> DocumentPageResponse:
    task = owned_task(db, task_id, user.id)
    task_risks = list(db.scalars(select(ReviewRisk).where(ReviewRisk.task_id == task.id)))
    prepare_document_snapshot(db, task, task_risks)
    try:
        page = document_service.get_page(task, page_number)
    except FileParseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    risk_ids = [
        risk.id
        for risk in task_risks
        if risk.locatable
        and risk.source_file_id == "main"
        and (
            any(
                int(span.get("page_number", 0)) == page_number
                for span in (risk.location_spans or [])
            )
            or (not risk.location_spans and risk.page_number == page_number)
        )
    ]
    return DocumentPageResponse(
        file_id="main",
        page_number=page_number,
        page_count=len(document_service.pages(task)),
        text=str(page.get("text", "")),
        blocks=page.get("blocks", []),
        ocr_used=bool(page.get("ocr_used", False)),
        text_source=str(page.get("text_source", "ocr" if page.get("ocr_used") else "native")),
        risk_ids=risk_ids,
    )


@router.get(
    "/{task_id}/documents/{file_id}/pages/{page_number:int}",
    response_model=DocumentPageResponse,
)
def get_material_page(
    task_id: int,
    file_id: str,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> DocumentPageResponse:
    task = owned_task(db, task_id, user.id)
    task_risks = list(db.scalars(select(ReviewRisk).where(ReviewRisk.task_id == task.id)))
    prepare_document_snapshot(db, task, task_risks)
    try:
        page = document_service.get_page(task, page_number, file_id)
        page_count = len(document_service.pages(task, file_id))
    except FileParseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    risk_ids = [
        risk.id
        for risk in task_risks
        if risk.locatable
        and risk.source_file_id == file_id
        and (
            any(
                int(span.get("page_number", 0)) == page_number
                for span in (risk.location_spans or [])
            )
            or (not risk.location_spans and risk.page_number == page_number)
        )
    ]
    return DocumentPageResponse(
        file_id=file_id,
        page_number=page_number,
        page_count=page_count,
        text=str(page.get("text", "")),
        blocks=page.get("blocks", []),
        ocr_used=bool(page.get("ocr_used", False)),
        text_source=str(page.get("text_source", "ocr" if page.get("ocr_used") else "native")),
        risk_ids=risk_ids,
    )


@router.get("/{task_id}/document/pages/{page_number:int}/image")
def get_document_page_image(
    task_id: int,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> Response:
    task = owned_task(db, task_id, user.id)
    prepare_document_snapshot(db, task)
    if page_number < 1 or page_number > document_meta(task).page_count:
        raise HTTPException(status_code=404, detail="文档页码不存在。")
    try:
        image = document_service.render_page_png(task, user.id, page_number)
    except (DocumentProcessingError, FileParseError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=image, media_type="image/png")


@router.get("/{task_id}/documents/{file_id}/pages/{page_number:int}/image")
def get_material_page_image(
    task_id: int,
    file_id: str,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> Response:
    task = owned_task(db, task_id, user.id)
    prepare_document_snapshot(db, task)
    try:
        meta = document_meta(task, file_id)
        if page_number < 1 or page_number > meta.page_count:
            raise FileParseError("文档页码不存在。")
        image = document_service.render_page_png(task, user.id, page_number, file_id)
    except (DocumentProcessingError, FileParseError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=image, media_type="image/png")


@router.get("/{task_id}/download")
def download_marked_document(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    export_format: Literal["original", "pdf"] = Query(default="original", alias="format"),
) -> FileResponse:
    task = owned_task(db, task_id, user.id)
    if task.status != "SUCCESS":
        raise HTTPException(status_code=409, detail="审查结果尚未生成。")
    risks = list(
        db.scalars(select(ReviewRisk).where(ReviewRisk.task_id == task.id).order_by(ReviewRisk.id))
    )
    prepare_document_snapshot(db, task, risks)
    source_extension = task.contract_name.rsplit(".", 1)[-1].lower()
    use_docx = source_extension == "docx" and export_format == "original"
    try:
        path = (
            document_service.generate_marked_docx(task, user.id, risks)
            if use_docx
            else document_service.generate_marked_pdf(task, user.id, risks)
        )
    except (DocumentProcessingError, FileParseError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    output_extension = "docx" if use_docx else "pdf"
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if use_docx
        else "application/pdf"
    )
    filename = f"{task.contract_name.rsplit('.', 1)[0]}_带标记版.{output_extension}"
    return FileResponse(path, media_type=media_type, filename=filename)


@router.post(
    "/{task_id}/risks/{risk_id}/feedback",
    response_model=RiskFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_risk_feedback(
    task_id: int,
    risk_id: int,
    request: RiskFeedbackCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> RiskFeedbackResponse:
    try:
        feedback = record_service.create_feedback(db, user.id, task_id, risk_id, request)
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewRecordValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RiskFeedbackResponse.model_validate(feedback, from_attributes=True)


@router.post("/{task_id}/retry", response_model=ReviewTaskResponse)
def retry_review(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> ReviewTaskResponse:
    task = owned_task(db, task_id, user.id)
    if task.status != "FAILED":
        raise HTTPException(status_code=409, detail="仅失败任务可以重新审查。")
    review_service.retry_task(db, task)
    background_tasks.add_task(review_service.run_review, task.id)
    return task_response(task)
