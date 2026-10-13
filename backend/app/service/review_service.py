import json
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.database.session import SessionLocal
from app.models.review import ReviewRisk, ReviewTask
from app.prompts.contract_review import build_review_messages
from app.schemas.review import ModelReviewOutput, ReviewCreateRequest
from app.service.file_service import FileParseError, FileService
from app.service.document_service import DocumentService
from app.service.model_service import ModelConfigurationError, ModelService
from app.service.scene_service import SceneNotFoundError, SceneService


PROCESS_STEPS = [
    "解析合同及附件",
    "读取场景与审查规则",
    "执行合同风险识别",
    "合并并校验风险",
    "生成审查结果",
]

INTERRUPTED_TASK_MESSAGE = "服务重启导致进程内审查任务中断，请点击重新审查。"


class ReviewService:
    task_statuses = {"PROCESSING", "SUCCESS", "FAILED"}

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        model_service_factory: Callable[[], ModelService] | None = None,
        file_service: FileService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.model_service_factory = model_service_factory
        self.file_service = file_service or FileService()
        self.document_service = DocumentService(
            self.file_service if isinstance(self.file_service, FileService) else None
        )
        self.scene_service = SceneService()

    def create_task(
        self,
        db: Session,
        request: ReviewCreateRequest,
        user_id: int,
        idempotency_key: str | None = None,
    ) -> tuple[ReviewTask, bool]:
        if idempotency_key:
            existing = db.scalar(
                select(ReviewTask).where(
                    ReviewTask.user_id == user_id,
                    ReviewTask.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing, False

        manifest = self.file_service.load_manifest(request.upload_id, user_id)
        main_file = manifest["main_file"]
        attachments = manifest["attachments"]
        if not str(main_file.get("content", "")).strip():
            raise FileParseError(
                main_file.get("ocr_message")
                or f"未能从文件“{main_file['file_name']}”中解析出可审查文本。"
            )
        total_characters = main_file["character_count"] + sum(
            item["character_count"] for item in attachments
        )
        if total_characters > settings.max_review_characters:
            raise FileParseError(
                f"合同材料解析文本超过 {settings.max_review_characters} 字符限制，请拆分或精简材料后重试。"
            )
        try:
            scene = self.scene_service.get_scene(db, request.scene_id)
        except SceneNotFoundError as exc:
            raise ReviewConfigurationError("所选审查场景不存在，请刷新后重新选择。") from exc
        if not scene.status:
            raise ReviewConfigurationError("所选审查场景已停用，请重新选择。")
        rules = self.scene_service.get_scene_rules(db, scene.id, only_enabled=True)
        if not rules:
            raise ReviewConfigurationError("所选审查场景暂无已启用规则，请重新选择。")
        scene_snapshot = self.scene_service.build_snapshot(scene, rules)
        try:
            model_snapshot = ModelService.configuration_snapshot(db)
        except ModelConfigurationError as exc:
            raise ReviewConfigurationError(str(exc)) from exc
        task = ReviewTask(
            task_no=self._make_task_no(),
            user_id=user_id,
            idempotency_key=idempotency_key,
            upload_id=request.upload_id,
            contract_name=main_file["file_name"],
            contract_text=main_file["content"],
            attachment_names=[item["file_name"] for item in attachments],
            attachment_texts=[
                {"file_name": item["file_name"], "content": item["content"]}
                for item in attachments
            ],
            scene_id=scene.id,
            scene_name=scene.scene_name,
            scene_snapshot=scene_snapshot,
            model_snapshot=model_snapshot,
            document_pages=main_file.get("pages", []),
            document_meta={
                "file_name": main_file["file_name"],
                "file_extension": main_file.get("file_extension", ""),
                "mime_type": main_file.get("mime_type", "application/octet-stream"),
                "page_count": main_file.get("page_count", 1),
                "ocr_used": main_file.get("ocr_used", False),
                "ocr_status": main_file.get("ocr_status", "not_required"),
                "ocr_message": main_file.get("ocr_message"),
                "text_source": main_file.get("text_source", "native"),
                "preview_available": main_file.get("preview_available", False),
                "pagination_source": main_file.get("pagination_source", "logical"),
                "office_text_source": main_file.get("office_text_source"),
                "preview_quality": main_file.get("preview_quality"),
            },
            document_files=[
                self.document_service.snapshot_file("main", main_file),
                *[
                    self.document_service.snapshot_file(f"attachment:{index}", item)
                    for index, item in enumerate(attachments, start=1)
                ],
            ],
            scale=request.scale,
            position=request.position,
            status="PROCESSING",
            progress=5,
            current_step=0,
            current_message="任务已创建，准备解析材料",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task, True

    def run_review(self, task_id: int) -> None:
        db = self.session_factory()
        try:
            task = db.get(ReviewTask, task_id)
            if not task:
                return
            self._update_progress(db, task, 0, 15, "合同及附件文本解析完成")
            rule_count = len((task.scene_snapshot or {}).get("rules", []))
            self._update_progress(db, task, 1, 30, f"已加载 {rule_count} 条场景审查规则")
            self._update_progress(db, task, 2, 55, "正在调用 AI 识别合同风险")

            model_service = (
                self.model_service_factory()
                if self.model_service_factory
                else ModelService.from_snapshot(db, task.model_snapshot)
            )
            raw_output = model_service.chat(build_review_messages(task))

            self._update_progress(db, task, 3, 82, "正在合并并校验风险结果")
            output = self.parse_model_output(raw_output)
            risks = self._normalize_risks(task, output)

            self._update_progress(db, task, 4, 94, "正在保存审查结果")
            db.execute(delete(ReviewRisk).where(ReviewRisk.task_id == task.id))
            for risk in risks:
                db.add(ReviewRisk(task_id=task.id, **risk))
            task.summary = output.summary
            task.status = "SUCCESS"
            task.progress = 100
            task.current_step = len(PROCESS_STEPS)
            task.current_message = "审查结果已生成"
            task.error_message = None
            task.complete_time = utc_now()
            db.commit()
        except Exception as exc:
            db.rollback()
            task = db.get(ReviewTask, task_id)
            if task:
                task.status = "FAILED"
                task.current_message = "审查任务执行失败"
                task.error_message = self._public_error(exc)
                db.commit()
        finally:
            db.close()

    def retry_task(self, db: Session, task: ReviewTask) -> None:
        db.execute(delete(ReviewRisk).where(ReviewRisk.task_id == task.id))
        task.status = "PROCESSING"
        task.progress = 5
        task.current_step = 0
        task.current_message = "正在重新审查"
        task.error_message = None
        task.summary = None
        task.complete_time = None
        db.commit()

    @staticmethod
    def recover_interrupted_tasks(db: Session) -> int:
        result = db.execute(
            update(ReviewTask)
            .where(ReviewTask.status == "PROCESSING")
            .values(
                status="FAILED",
                current_message="审查任务已中断",
                error_message=INTERRUPTED_TASK_MESSAGE,
                complete_time=utc_now(),
            )
        )
        db.commit()
        return int(result.rowcount or 0)

    @staticmethod
    def parse_model_output(raw_output: str) -> ModelReviewOutput:
        content = raw_output.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型未返回有效的 JSON 审查结果。")
        try:
            payload = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("模型返回的审查结果不是有效 JSON。") from exc
        return ModelReviewOutput.model_validate(payload)

    def _normalize_risks(
        self, task: ReviewTask, output: ModelReviewOutput
    ) -> list[dict[str, Any]]:
        allowed_rules = {
            rule["rule_id"]: rule for rule in (task.scene_snapshot or {}).get("rules", [])
        }
        if not allowed_rules:
            raise ValueError("任务规则快照为空。")
        documents = {item["file_id"]: item for item in self.document_service.documents(task)}
        seen: set[tuple[str, str, str, int | None]] = set()
        normalized: list[dict[str, Any]] = []

        for risk in output.risks:
            if risk.rule_id not in allowed_rules:
                raise ValueError(f"模型返回了任务规则快照之外的规则：{risk.rule_id}")
            duplicate_key = (
                risk.name.strip(),
                (risk.original_text or "").strip(),
                (risk.source_file_id or risk.source or "").strip(),
                risk.page_number,
            )
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)

            original_text = (risk.original_text or "").strip() or None
            context_before = (risk.context_before or "").strip() or None
            context_after = (risk.context_after or "").strip() or None
            location_hint = {
                "page_number": risk.page_number,
                "context_before": context_before,
                "context_after": context_after,
                "rule_id": risk.rule_id,
            }
            source_file_id = (
                risk.source_file_id if risk.source_file_id in documents else None
            )
            if not source_file_id:
                source_file_id = self.document_service._source_file_id(task, risk.source)
            source = (
                str(documents[source_file_id]["file_name"])
                if source_file_id in documents
                else None
            )
            location = None
            if original_text and source_file_id:
                location = self.document_service.locate_text(
                    task,
                    source,
                    original_text,
                    source_file_id=source_file_id,
                    page_number=risk.page_number,
                    context_before=context_before,
                    context_after=context_after,
                )
            elif original_text:
                matched_locations = []
                for file_id, document in documents.items():
                    matched = self.document_service.locate_text(
                        task,
                        str(document["file_name"]),
                        original_text,
                        source_file_id=file_id,
                        page_number=risk.page_number,
                        context_before=context_before,
                        context_after=context_after,
                    )
                    if matched:
                        matched_locations.append((file_id, document, matched))
                if len(matched_locations) == 1:
                    source_file_id, document, location = matched_locations[0]
                    source = str(document["file_name"])
            primary = (location or {}).get("location_spans", [{}])[0]
            normalized.append(
                {
                    "risk_name": risk.name.strip(),
                    "risk_level": risk.level,
                    "rule_id": risk.rule_id,
                    "rule_name": allowed_rules[risk.rule_id]["rule_name"],
                    "original_text": original_text,
                    "source": source or "需人工核验",
                    "locatable": bool(location),
                    "description": risk.description.strip(),
                    "suggestion": risk.suggestion.strip(),
                    "page_number": primary.get("page_number") if location else None,
                    "source_file_id": (
                        primary.get("source_file_id")
                        if location
                        else source_file_id
                    ),
                    "block_id": primary.get("block_id") if location else None,
                    "start_offset": primary.get("start_offset") if location else None,
                    "end_offset": primary.get("end_offset") if location else None,
                    "anchor_text": (
                        primary.get("anchor_text") if location else original_text
                    ),
                    "anchor_hash": primary.get("anchor_hash") if location else None,
                    "location_spans": location.get("location_spans", []) if location else [],
                    "location_hint": location_hint,
                }
            )
        return normalized

    @staticmethod
    def _update_progress(
        db: Session, task: ReviewTask, step: int, progress: int, message: str
    ) -> None:
        task.current_step = step
        task.progress = progress
        task.current_message = message
        db.commit()

    @staticmethod
    def _make_task_no() -> str:
        return f"CR{utc_now():%Y%m%d%H%M%S}{uuid4().hex[:4].upper()}"

    @staticmethod
    def _public_error(exc: Exception) -> str:
        message = str(exc).strip() or "未知错误"
        if "API Key" in message:
            return message
        if isinstance(exc, ValueError):
            return f"审查结果校验失败：{message}"
        return f"AI 审查服务暂时不可用：{message[:300]}"


class ReviewConfigurationError(ValueError):
    pass
