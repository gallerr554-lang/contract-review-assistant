import shutil
import subprocess
from dataclasses import asdict, dataclass
from functools import lru_cache

from app.core.config import settings


@dataclass(frozen=True)
class OcrRuntimeStatus:
    available: bool
    status: str
    message: str
    pdftoppm_available: bool
    tesseract_available: bool
    requested_languages: list[str]
    installed_languages: list[str]
    missing_languages: list[str]

    def model_dump(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def get_ocr_runtime_status() -> OcrRuntimeStatus:
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    requested = [item for item in settings.ocr_language.split("+") if item]
    installed: list[str] = []

    if tesseract:
        try:
            result = subprocess.run(
                [tesseract, "--list-langs"],
                capture_output=True,
                check=False,
                timeout=10,
                text=True,
            )
            if result.returncode == 0:
                installed = sorted(
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip() and not line.lower().startswith("list of available languages")
                )
        except (OSError, subprocess.SubprocessError):
            installed = []

    missing_languages = [language for language in requested if language not in installed]
    if not pdftoppm:
        message = "OCR 不可用：未安装 Poppler 页面渲染组件 pdftoppm。"
    elif not tesseract:
        message = "OCR 不可用：未安装 Tesseract。扫描页将保留失败提示并降级为人工核验。"
    elif missing_languages:
        message = f"OCR 不可用：Tesseract 缺少语言包 {', '.join(missing_languages)}。"
    else:
        message = f"OCR 已就绪，识别语言：{settings.ocr_language}。"

    available = bool(pdftoppm and tesseract and not missing_languages)
    return OcrRuntimeStatus(
        available=available,
        status="ready" if available else "degraded",
        message=message,
        pdftoppm_available=bool(pdftoppm),
        tesseract_available=bool(tesseract),
        requested_languages=requested,
        installed_languages=installed,
        missing_languages=missing_languages,
    )
