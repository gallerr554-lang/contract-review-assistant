"""Run a real configured-model review without printing credentials or ciphertext."""

import argparse
import hmac
import json
from pathlib import Path

from sqlalchemy import select

from app.api.review import get_review_result
from app.core.config import settings
from app.core.time import utc_now
from app.database.session import SessionLocal
from app.models.model_config import ModelConfig
from app.models.review import ReviewRisk, ReviewTask
from app.models.scene import ReviewScene
from app.models.user import User
from app.schemas.review import ReviewCreateRequest
from app.service.file_service import FileService
from app.service.model_config_service import ModelConfigService
from app.service.model_service import ModelService
from app.service.review_service import ReviewService
from app.service.scene_service import SceneService


def _select_manifest(file_service: FileService, user_id: int, upload_id: str | None) -> dict:
    if upload_id:
        return file_service.load_manifest(upload_id, user_id)
    manifests = []
    for path in file_service.contract_root.glob("*/manifest.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("user_id") == user_id and data.get("main_file", {}).get("content", "").strip():
            manifests.append(data)
    if not manifests:
        raise RuntimeError("当前用户没有可用于冒烟测试的已解析合同。")
    return min(manifests, key=lambda item: item["main_file"].get("character_count", 0))


def _select_scene(db, scene_id: int | None) -> ReviewScene:
    scene_service = SceneService()
    scenes = [
        scene
        for scene in db.scalars(
            select(ReviewScene).where(ReviewScene.status.is_(True)).order_by(ReviewScene.id)
        )
        if scene_service.get_scene_rules(db, scene.id, only_enabled=True)
    ]
    if scene_id:
        scenes = [scene for scene in scenes if scene.id == scene_id]
    if not scenes:
        raise RuntimeError("没有包含启用规则的可用审查场景。")
    return scenes[0]


def run(
    user_id: int | None,
    upload_id: str | None,
    scene_id: int | None,
    refresh_key_from_env: bool,
    provider: str = "deepseek",
) -> dict:
    db = SessionLocal()
    try:
        config = db.scalar(select(ModelConfig).where(
            ModelConfig.status.is_(True), ModelConfig.provider == provider
        ).order_by(ModelConfig.id).limit(1))
        if not config:
            raise RuntimeError(f"没有找到系统当前启用的 {provider} 模型配置。")
        user = db.get(User, user_id) if user_id else db.scalar(select(User).order_by(User.id))
        if not user:
            raise RuntimeError("没有找到可用于冒烟测试的业务用户。")

        config_service = ModelConfigService()
        key_refreshed = refresh_key_from_env or not config.api_key_encrypted
        if key_refreshed:
            if not settings.model_api_key:
                raise RuntimeError(f"当前 {provider} 配置和环境变量均未提供 API Key。")
            config.api_key_encrypted = config_service.cipher.encrypt(settings.model_api_key)
            config.update_time = utc_now()
            db.commit()
            db.refresh(config)

        resolved_key = config_service.resolve_api_key(config)
        if not resolved_key:
            raise RuntimeError("API Key 解密失败。")
        if key_refreshed and settings.model_api_key and not hmac.compare_digest(
            resolved_key.encode("utf-8"), settings.model_api_key.encode("utf-8")
        ):
            raise RuntimeError("解密后的 API Key 与当前环境配置不一致。")

        file_service = FileService()
        manifest = _select_manifest(file_service, user.id, upload_id)
        scene = _select_scene(db, scene_id)
        service = ReviewService(file_service=file_service)
        task, _ = service.create_task(
            db,
            ReviewCreateRequest(
                upload_id=manifest["upload_id"],
                scene_id=scene.id,
                scale="标准",
                position="甲方",
            ),
            user.id,
        )
        task_id = task.id
        snapshot = task.model_snapshot or {}
        snapshot_service = ModelService.from_snapshot(db, snapshot)
        system_key_resolution_ok = bool(
            snapshot_service.api_key
            and hmac.compare_digest(
                snapshot_service.api_key.encode("utf-8"), resolved_key.encode("utf-8")
            )
        )
    finally:
        db.close()

    ReviewService().run_review(task_id)

    db = SessionLocal()
    try:
        task = db.get(ReviewTask, task_id)
        user = db.get(User, task.user_id) if task else None
        if not task or not user:
            raise RuntimeError("冒烟任务未保存。")
        risk_count = len(
            list(db.scalars(select(ReviewRisk.id).where(ReviewRisk.task_id == task.id)))
        )
        result_serializable = False
        if task.status == "SUCCESS":
            result = get_review_result(task.id, db, user)
            result_serializable = bool(result.model_dump(mode="json").get("summary"))
        return {
            "task_id": task.id,
            "provider": task.model_snapshot.get("provider"),
            "model_name": task.model_snapshot.get("model_name"),
            "status": task.status,
            "risk_count": risk_count,
            "summary_saved": bool(task.summary),
            "snapshot_has_user": "user_id" in task.model_snapshot,
            "snapshot_has_key": "api_key_encrypted" in task.model_snapshot,
            "system_key_resolution_ok": system_key_resolution_ok,
            "result_serializable": result_serializable,
            "error": task.error_message if task.status == "FAILED" else None,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--upload-id")
    parser.add_argument("--scene-id", type=int)
    parser.add_argument("--refresh-key-from-env", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.user_id, args.upload_id, args.scene_id, args.refresh_key_from_env),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
