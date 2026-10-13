from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.main import app
from app.models import Base
from app.models.review import ReviewRisk, ReviewTask
from app.models.user import User


def test_result_api_backfills_historical_locations_and_keeps_shared_anchor() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    db = testing_session()
    user = User(
        email="document-api@example.com",
        password_hash="test-only",
        role="user",
        status=True,
    )
    db.add(user)
    db.flush()
    task = ReviewTask(
        task_no="CR-HISTORICAL-DOCUMENT",
        user_id=user.id,
        upload_id="9" * 36,
        contract_name="中文采购合同.txt",
        contract_text="第一条 合同金额\n第二条 验收后十日内付款。",
        attachment_names=[],
        attachment_texts=[],
        scene_name="采购合同",
        scene_snapshot={"rules": []},
        model_snapshot={},
        document_pages=[
            {
                "page_number": 1,
                "text": "第一条 合同金额\n第二条 验收后十日内付款。",
                "blocks": [],
            }
        ],
        document_meta={"page_count": 1},
        scale="标准",
        position="甲方",
        status="SUCCESS",
        progress=100,
        current_step=5,
        current_message="完成",
        summary="付款条件需要核验。",
    )
    db.add(task)
    db.flush()
    for index in range(2):
        db.add(
            ReviewRisk(
                task_id=task.id,
                rule_id=f"R00{index + 1}",
                rule_name="付款审查",
                risk_name=f"付款风险 {index + 1}",
                risk_level="medium",
                original_text="验收后十日内付款",
                source=task.contract_name,
                locatable=False,
                description="付款节点需要核验。",
                suggestion="明确付款前提。",
            )
        )
    db.commit()
    task_id = task.id
    user_id = user.id
    db.close()

    def override_get_db() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    def override_current_user() -> User:
        session = testing_session()
        try:
            return session.get(User, user_id)
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    try:
        response = client.get(f"/api/review/{task_id}/result")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["risks"]) == 2
        assert [item["file_id"] for item in payload["documents"]] == ["main"]
        assert all(len(item["location_spans"]) == 1 for item in payload["risks"])
        anchors = {
            (
                item["source_file_id"],
                item["page_number"],
                item["block_id"],
                item["start_offset"],
                item["end_offset"],
                item["anchor_text"],
                item["anchor_hash"],
            )
            for item in payload["risks"]
        }
        assert len(anchors) == 1
        anchor = next(iter(anchors))
        assert anchor[0:3] == ("main", 1, "p1:b2")
        assert anchor[3] < anchor[4]
        assert anchor[5] == "验收后十日内付款"
        assert len(anchor[6]) == 64

        page_response = client.get(f"/api/review/{task_id}/document/pages/1")
        assert page_response.status_code == 200
        page_payload = page_response.json()
        assert len(page_payload["risk_ids"]) == 2
        assert [block["block_id"] for block in page_payload["blocks"]] == [
            "p1:b1",
            "p1:b2",
        ]

        verify_db = testing_session()
        try:
            stored = list(
                verify_db.scalars(
                    select(ReviewRisk).where(ReviewRisk.task_id == task_id).order_by(ReviewRisk.id)
                )
            )
            assert all(item.locatable and item.anchor_hash for item in stored)
            assert stored[0].anchor_hash == stored[1].anchor_hash
        finally:
            verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_attachment_page_api_restores_location_from_task_snapshot() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    db = testing_session()
    user = User(email="attachment-api@example.com", password_hash="test-only", role="user", status=True)
    db.add(user)
    db.flush()
    main_pages = [{"page_number": 1, "text": "主合同正文。", "blocks": [{"block_id": "p1:b1", "type": "paragraph", "text": "主合同正文。"}]}]
    attachment_pages = [{"page_number": 1, "text": "验收不合格时，乙方应在五日内整改。", "blocks": [{"block_id": "p1:b1", "type": "paragraph", "text": "验收不合格时，乙方应在五日内整改。"}]}]
    task = ReviewTask(
        task_no="CR-ATTACHMENT-API",
        user_id=user.id,
        upload_id="8" * 36,
        contract_name="主合同.txt",
        contract_text="主合同正文。",
        attachment_names=["技术附件.docx"],
        attachment_texts=[{"file_name": "技术附件.docx", "content": attachment_pages[0]["text"]}],
        scene_name="采购合同",
        scene_snapshot={"rules": []},
        model_snapshot={},
        document_pages=main_pages,
        document_meta={"file_name": "主合同.txt", "file_extension": "txt", "page_count": 1},
        document_files=[
            {"file_id": "main", "file_name": "主合同.txt", "file_extension": "txt", "pages": main_pages},
            {"file_id": "attachment:1", "file_name": "技术附件.docx", "file_extension": "docx", "pages": attachment_pages},
        ],
        scale="标准",
        position="甲方",
        status="SUCCESS",
        progress=100,
        current_step=5,
        current_message="完成",
        summary="附件整改期限需要核验。",
    )
    db.add(task)
    db.flush()
    db.add(
        ReviewRisk(
            task_id=task.id,
            rule_id="R001",
            rule_name="附件审查",
            risk_name="整改期限",
            risk_level="medium",
            original_text="乙方应在五日内整改",
            source="技术附件.docx",
            source_file_id="attachment:1",
            locatable=False,
            description="整改期限需要确认。",
            suggestion="明确整改验收要求。",
            location_hint={"page_number": 1},
        )
    )
    db.commit()
    task_id, user_id = task.id, user.id
    db.close()

    def override_get_db() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    def override_current_user() -> User:
        session = testing_session()
        try:
            return session.get(User, user_id)
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    try:
        result_response = client.get(f"/api/review/{task_id}/result")
        assert result_response.status_code == 200
        payload = result_response.json()
        assert [item["file_id"] for item in payload["documents"]] == ["main", "attachment:1"]
        assert payload["risks"][0]["locatable"] is True
        assert payload["risks"][0]["location_spans"][0]["source_file_id"] == "attachment:1"

        page_response = client.get(
            f"/api/review/{task_id}/documents/attachment%3A1/pages/1"
        )
        assert page_response.status_code == 200
        page_payload = page_response.json()
        assert page_payload["file_id"] == "attachment:1"
        assert page_payload["risk_ids"] == [payload["risks"][0]["id"]]
    finally:
        app.dependency_overrides.clear()
