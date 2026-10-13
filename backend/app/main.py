from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.database.session import SessionLocal
from app.service.auth_service import AuthService
from app.service.review_service import ReviewService
from app.service.runtime_service import get_ocr_runtime_status


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = SessionLocal()
    try:
        AuthService().ensure_initial_admin(db)
        recovered = ReviewService.recover_interrupted_tasks(db)
        if recovered:
            logger.warning("Marked %s interrupted review task(s) as failed.", recovered)
    finally:
        db.close()
    ocr = get_ocr_runtime_status()
    log_ocr = logger.info if ocr.available else logger.warning
    log_ocr("OCR runtime status: %s", ocr.message)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="合同审查助手 API",
        description="合同上传、文本解析、AI 审查和结构化风险结果服务。",
        version="0.2.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
