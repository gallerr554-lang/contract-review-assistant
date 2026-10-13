from fastapi import APIRouter
from sqlalchemy import text

from app.database.session import engine
from app.service.runtime_service import get_ocr_runtime_status

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("select 1"))
    return {"status": "ok"}


@router.get("/health/runtime")
def runtime_health_check() -> dict:
    ocr = get_ocr_runtime_status()
    return {
        "status": "ok" if ocr.available else "degraded",
        "ocr": ocr.model_dump(),
    }
