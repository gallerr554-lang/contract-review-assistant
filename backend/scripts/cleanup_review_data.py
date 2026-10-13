"""Delete review history and generated files without touching configuration data."""

import argparse
import json
import shutil
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.review import ReviewRisk, ReviewRiskFeedback, ReviewTask
from app.models.rule import ReviewRule
from app.models.scene import ReviewScene, SceneRuleRelation
from app.models.user import User


CONFIRMATION = "DELETE_REVIEW_HISTORY"
TASK_STORAGE_DIRECTORIES = ("contracts", "attachments", "results", "tmp", "temp")


def database_counts(db: Session) -> dict[str, int]:
    models = {
        "tasks": ReviewTask,
        "risks": ReviewRisk,
        "feedback": ReviewRiskFeedback,
        "users": User,
        "rules": ReviewRule,
        "scenes": ReviewScene,
        "scene_rule_relations": SceneRuleRelation,
    }
    return {
        name: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for name, model in models.items()
    }


def cleanup_database(db: Session) -> dict[str, int]:
    deleted = {
        "feedback": int(db.execute(delete(ReviewRiskFeedback)).rowcount or 0),
        "risks": int(db.execute(delete(ReviewRisk)).rowcount or 0),
        "tasks": int(db.execute(delete(ReviewTask)).rowcount or 0),
    }
    db.commit()
    return deleted


def cleanup_storage(storage_root: str | Path) -> dict[str, int]:
    root = Path(storage_root).resolve()
    if root == Path(root.anchor) or len(root.parts) < 3:
        raise RuntimeError(f"拒绝清理不安全的存储路径：{root}")

    removed: dict[str, int] = {}
    for name in TASK_STORAGE_DIRECTORIES:
        directory = root / name
        count = 0
        if directory.is_dir():
            for child in directory.iterdir():
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
                count += 1
        else:
            directory.mkdir(parents=True, exist_ok=True)
        removed[name] = count
    return removed


def run_cleanup(storage_root: str | Path | None = None) -> dict:
    db = SessionLocal()
    try:
        before = database_counts(db)
        deleted = cleanup_database(db)
        after = database_counts(db)
    finally:
        db.close()
    removed = cleanup_storage(storage_root or settings.storage_root)
    return {"before": before, "deleted": deleted, "after": after, "storage_removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="清理审查任务、风险、反馈和生成文件，保留用户、规则与场景。"
    )
    parser.add_argument("--confirm", help=f"执行删除必须填写：{CONFIRMATION}")
    parser.add_argument("--dry-run", action="store_true", help="仅显示数据库统计，不删除数据")
    args = parser.parse_args()

    if args.dry_run:
        db = SessionLocal()
        try:
            print(json.dumps({"dry_run": True, "counts": database_counts(db)}, ensure_ascii=False))
        finally:
            db.close()
        return
    if args.confirm != CONFIRMATION:
        parser.error(f"拒绝执行：请显式传入 --confirm {CONFIRMATION}")

    print(json.dumps(run_cleanup(), ensure_ascii=False))


if __name__ == "__main__":
    main()
