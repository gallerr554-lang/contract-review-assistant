from collections.abc import Generator
from subprocess import CompletedProcess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.core.config import Settings
from app.models.review import ReviewTask
from app.service.review_service import INTERRUPTED_TASK_MESSAGE, ReviewService
from app.service.runtime_service import get_ocr_runtime_status


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def make_task(status: str, number: str) -> ReviewTask:
    return ReviewTask(
        task_no=number,
        user_id=None,
        upload_id="a" * 36,
        contract_name="恢复测试合同.txt",
        contract_text="合同正文",
        attachment_names=[],
        attachment_texts=[],
        scene_name="测试场景",
        scene_snapshot={"rules": []},
        model_snapshot={},
        document_pages=[],
        document_meta={},
        scale="标准",
        position="甲方",
        status=status,
        progress=55 if status == "PROCESSING" else 100,
        current_step=2,
        current_message="测试状态",
    )


def test_ocr_runtime_reports_missing_tesseract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_ocr_runtime_status.cache_clear()
    monkeypatch.setattr(
        "app.service.runtime_service.shutil.which",
        lambda name: "/usr/local/bin/pdftoppm" if name == "pdftoppm" else None,
    )

    status = get_ocr_runtime_status()

    assert status.available is False
    assert status.status == "degraded"
    assert "Tesseract" in status.message
    get_ocr_runtime_status.cache_clear()


def test_ocr_runtime_requires_all_configured_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_ocr_runtime_status.cache_clear()
    monkeypatch.setattr(
        "app.service.runtime_service.shutil.which", lambda name: f"/usr/local/bin/{name}"
    )
    monkeypatch.setattr(
        "app.service.runtime_service.subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess(
            args=[], returncode=0, stdout="List of available languages (1):\neng\n", stderr=""
        ),
    )

    status = get_ocr_runtime_status()

    assert status.available is False
    assert "chi_sim" in status.missing_languages
    assert "语言包" in status.message
    get_ocr_runtime_status.cache_clear()


def test_recover_interrupted_task_preserves_retry_flow(db: Session) -> None:
    interrupted = make_task("PROCESSING", "CR-INTERRUPTED")
    completed = make_task("SUCCESS", "CR-COMPLETED")
    db.add_all([interrupted, completed])
    db.commit()

    recovered = ReviewService.recover_interrupted_tasks(db)
    db.refresh(interrupted)
    db.refresh(completed)

    assert recovered == 1
    assert interrupted.status == "FAILED"
    assert interrupted.current_message == "审查任务已中断"
    assert interrupted.error_message == INTERRUPTED_TASK_MESSAGE
    assert interrupted.complete_time is not None
    assert completed.status == "SUCCESS"

    ReviewService().retry_task(db, interrupted)
    assert interrupted.status == "PROCESSING"
    assert interrupted.error_message is None
    assert interrupted.complete_time is None


def test_settings_build_database_url_for_compose_exec() -> None:
    configured = Settings(
        _env_file=None,
        database_url=None,
        postgres_host="postgres",
        postgres_port=5432,
        postgres_db="contract/review",
        postgres_user="user@local",
        postgres_password="p:a/s#%",
    )

    assert configured.database_url == (
        "postgresql+psycopg://user%40local:p%3Aa%2Fs%23%25@"
        "postgres:5432/contract%2Freview"
    )
