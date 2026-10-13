import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4
from xml.sax.saxutils import escape

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import settings
from app.service.runtime_service import get_ocr_runtime_status


class FileParseError(ValueError):
    pass


class FileService:
    allowed_extensions = {"doc", "docx", "pdf", "txt"}
    max_attachment_count = 3

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root or settings.storage_root).resolve()
        self.contract_root = self.storage_root / "contracts"
        self.contract_root.mkdir(parents=True, exist_ok=True)

    async def save_and_parse(
        self,
        main_file: UploadFile,
        attachments: list[UploadFile],
        user_id: int,
    ) -> dict:
        if len(attachments) > self.max_attachment_count:
            raise FileParseError("合同附件最多上传 3 份。")

        upload_id = str(uuid4())
        upload_dir = self.contract_root / upload_id
        upload_dir.mkdir(parents=True)

        parsed_main = await self._save_file(main_file, upload_dir, "main")
        parsed_attachments = [
            await self._save_file(file, upload_dir, f"attachment-{index}")
            for index, file in enumerate(attachments, start=1)
        ]
        manifest = {
            "upload_id": upload_id,
            "user_id": user_id,
            "main_file": parsed_main,
            "attachments": parsed_attachments,
        }
        (upload_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        return manifest

    def load_manifest(self, upload_id: str, user_id: int) -> dict:
        if not upload_id or Path(upload_id).name != upload_id:
            raise FileParseError("上传标识无效。")
        manifest_path = self.contract_root / upload_id / "manifest.json"
        if not manifest_path.is_file():
            raise FileParseError("上传材料不存在或已失效，请重新上传。")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("user_id") != user_id:
            raise FileParseError("上传材料不存在或不属于当前账号。")
        self._resolve_manifest_paths(manifest, manifest_path.parent)
        return manifest

    @staticmethod
    def _resolve_manifest_paths(manifest: dict, upload_dir: Path) -> None:
        materials = [manifest.get("main_file"), *(manifest.get("attachments") or [])]
        for material in materials:
            if not isinstance(material, dict):
                continue
            for field in ("stored_path", "preview_path"):
                raw_path = str(material.get(field) or "")
                if not raw_path or Path(raw_path).is_file():
                    continue
                mounted_path = upload_dir / Path(raw_path).name
                if mounted_path.is_file():
                    material[field] = str(mounted_path)

    def claim_manifest(self, upload_id: str, user_id: int) -> None:
        manifest_path = self.contract_root / upload_id / "manifest.json"
        if not manifest_path.is_file():
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("user_id") is None:
            manifest["user_id"] = user_id
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    async def _save_file(self, upload: UploadFile, upload_dir: Path, prefix: str) -> dict:
        original_name = Path(unquote(upload.filename or "")).name
        extension = Path(original_name).suffix.lower().lstrip(".")
        if not original_name or extension not in self.allowed_extensions:
            raise FileParseError(
                f"文件“{original_name or '未命名文件'}”格式不支持，请上传 DOC、DOCX、PDF 或 TXT 文件。"
            )

        content = await upload.read()
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if not content:
            raise FileParseError(f"文件“{original_name}”内容为空。")
        if len(content) > max_bytes:
            raise FileParseError(f"文件“{original_name}”超过 {settings.max_file_size_mb} MB 限制。")

        stored_path = upload_dir / f"{prefix}.{extension}"
        stored_path.write_bytes(content)
        parsed = self.parse_document(stored_path, extension)
        text = parsed["content"]
        if not text.strip() and not (
            extension == "pdf" and parsed.get("ocr_status") in {"unavailable", "failed"}
        ):
            raise FileParseError(f"未能从文件“{original_name}”中解析出文本内容。")
        return {
            "file_name": original_name,
            "stored_path": str(stored_path),
            "file_extension": extension,
            "mime_type": self._mime_type(extension),
            "content": text.strip(),
            "character_count": len(text.strip()),
            **{key: value for key, value in parsed.items() if key != "content"},
        }

    def parse_file(self, path: Path, extension: str | None = None) -> str:
        return str(self.parse_document(path, extension)["content"])

    def parse_document(self, path: Path, extension: str | None = None) -> dict:
        file_extension = (extension or path.suffix.lstrip(".")).lower()
        try:
            if file_extension == "txt":
                text = self._parse_txt(path)
                pages = self._paginate_blocks(self._text_blocks(text))
                result = self._document_result(pages, "not_required", False, None, False)
                result["pagination_source"] = "logical"
                return result
            if file_extension == "docx":
                document = Document(path)
                blocks = self._docx_blocks(document)
                preview = self._convert_office_to_pdf(path)
                pages = self._office_pages(blocks, preview)
                preview_usable = self._office_preview_is_usable(preview)
                result = self._document_result(
                    pages, "not_required", False, None, preview_usable
                )
                if preview:
                    result["preview_path"] = str(preview)
                result["pagination_source"] = "physical_pdf" if preview else "logical"
                result["office_text_source"] = "structured"
                result["preview_quality"] = (
                    "usable" if preview_usable else "unusable" if preview else "unavailable"
                )
                return result
            if file_extension == "pdf":
                result = self._parse_pdf(path)
                result["pagination_source"] = "physical_pdf"
                return result
            if file_extension == "doc":
                text = self._parse_doc(path)
                blocks = self._text_blocks(text)
                preview = self._convert_office_to_pdf(path)
                pages = self._office_pages(blocks, preview)
                preview_usable = self._office_preview_is_usable(preview)
                result = self._document_result(
                    pages, "not_required", False, None, preview_usable
                )
                if preview:
                    result["preview_path"] = str(preview)
                result["pagination_source"] = "physical_pdf" if preview else "logical"
                result["office_text_source"] = "structured"
                result["preview_quality"] = (
                    "usable" if preview_usable else "unusable" if preview else "unavailable"
                )
                return result
        except FileParseError:
            raise
        except Exception as exc:
            raise FileParseError(f"文件“{path.name}”解析失败，请确认文件未损坏或加密。") from exc
        raise FileParseError(f"文件“{path.name}”格式不支持。")

    def _parse_pdf(self, path: Path) -> dict:
        reader = PdfReader(path)
        pages: list[dict] = []
        ocr_used = False
        ocr_failures: list[int] = []
        ocr_unavailable_message: str | None = None
        for index, page in enumerate(reader.pages, start=1):
            text = self._extract_pdf_text(page)
            page_ocr = False
            native_usable = self._text_is_usable(text)
            if not native_usable:
                text = ""
            if len(text) < settings.ocr_min_page_characters or not native_usable:
                try:
                    ocr_text = self._ocr_pdf_page(path, index).strip()
                    if ocr_text:
                        text = ocr_text
                        page_ocr = True
                        ocr_used = True
                    else:
                        ocr_failures.append(index)
                except OcrUnavailableError as exc:
                    ocr_unavailable_message = str(exc)
                except OcrProcessingError:
                    ocr_failures.append(index)
            blocks = self._text_blocks(text)
            pages.append(
                {
                    "page_number": index,
                    "text": text,
                    "blocks": blocks,
                    "ocr_used": page_ocr,
                    "text_source": "ocr" if page_ocr else ("native" if text else "unavailable"),
                }
            )
        if ocr_unavailable_message:
            status = "unavailable"
            message = ocr_unavailable_message
        elif ocr_failures:
            status = "partial" if any(page["text"] for page in pages) else "failed"
            message = f"第 {', '.join(map(str, ocr_failures))} 页 OCR 识别失败，请人工核验。"
        elif ocr_used:
            status = "success"
            message = "扫描页已通过 OCR 识别，结果请结合原件核验。"
        else:
            status = "not_required"
            message = None
        return self._document_result(pages, status, ocr_used, message, True)

    @staticmethod
    def _ocr_pdf_page(path: Path, page_number: int) -> str:
        runtime = get_ocr_runtime_status()
        if not runtime.available:
            raise OcrUnavailableError(runtime.message)
        pdftoppm = shutil.which("pdftoppm")
        tesseract = shutil.which("tesseract")
        if not pdftoppm or not tesseract:
            raise OcrUnavailableError(runtime.message)
        with tempfile.TemporaryDirectory(prefix="contract-ocr-") as temp_dir:
            output_prefix = Path(temp_dir) / "page"
            render = subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-singlefile",
                    "-png",
                    "-r",
                    "220",
                    str(path),
                    str(output_prefix),
                ],
                capture_output=True,
                check=False,
                timeout=settings.ocr_timeout_seconds,
            )
            image_path = output_prefix.with_suffix(".png")
            if render.returncode != 0 or not image_path.is_file():
                raise OcrProcessingError
            result = subprocess.run(
                [
                    tesseract,
                    str(image_path),
                    "stdout",
                    "-l",
                    settings.ocr_language,
                    "--psm",
                    "6",
                ],
                capture_output=True,
                check=False,
                timeout=settings.ocr_timeout_seconds,
            )
            if result.returncode != 0:
                raise OcrProcessingError
            return result.stdout.decode("utf-8", errors="replace")

    @staticmethod
    def _docx_blocks(document: DocumentObject) -> list[dict]:
        blocks: list[dict] = []
        for child in document.element.body.iterchildren():
            if isinstance(child, CT_P):
                paragraph = Paragraph(child, document)
                text = paragraph.text.strip()
                if text:
                    style = paragraph.style.name if paragraph.style else ""
                    blocks.append({"type": "paragraph", "text": text, "style": style})
                if 'w:type="page"' in child.xml:
                    blocks.append({"type": "page_break", "text": ""})
            elif isinstance(child, CT_Tbl):
                table = Table(child, document)
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                text = "\n".join(" | ".join(row) for row in rows)
                if text.strip():
                    blocks.append({"type": "table", "text": text, "rows": rows})
        return blocks

    @staticmethod
    def _text_blocks(text: str) -> list[dict]:
        paragraphs = [item.strip() for item in text.replace("\r\n", "\n").split("\n")]
        return [{"type": "paragraph", "text": item} for item in paragraphs if item]

    @staticmethod
    def _document_result(
        pages: list[dict],
        ocr_status: str,
        ocr_used: bool,
        ocr_message: str | None,
        preview_available: bool,
    ) -> dict:
        normalized = []
        for index, page in enumerate(pages, start=1):
            page_number = int(page.get("page_number", index))
            page_text = str(page.get("text", "")).strip()
            raw_blocks = page.get("blocks", []) or (
                FileService._text_blocks(page_text) if page_text else []
            )
            blocks = []
            for block_index, block in enumerate(raw_blocks, start=1):
                blocks.append(
                    {
                        **block,
                        "block_id": str(
                            block.get("block_id") or f"p{page_number}:b{block_index}"
                        ),
                    }
                )
            normalized.append(
                {
                    **page,
                    "page_number": page_number,
                    "text": page_text,
                    "blocks": blocks,
                    "ocr_used": bool(page.get("ocr_used", False)),
                    "text_source": str(
                        page.get(
                            "text_source",
                            "ocr" if page.get("ocr_used") else "native",
                        )
                    ),
                }
            )
        ocr_page_count = sum(1 for page in normalized if page["ocr_used"])
        if ocr_page_count == len(normalized) and ocr_page_count:
            text_source = "ocr"
        elif ocr_page_count:
            text_source = "mixed"
        elif ocr_status in {"failed", "unavailable"} and not any(
            page["text"] for page in normalized
        ):
            text_source = "unavailable"
        else:
            text_source = "native"
        return {
            "content": "\n\n".join(page["text"] for page in normalized if page["text"]),
            "pages": normalized,
            "page_count": max(1, len(normalized)),
            "ocr_used": ocr_used,
            "ocr_status": ocr_status,
            "ocr_message": ocr_message,
            "text_source": text_source,
            "preview_available": preview_available,
        }

    @staticmethod
    def _paginate_blocks(blocks: list[dict]) -> list[dict]:
        if not blocks:
            return [{"page_number": 1, "text": "", "blocks": [], "ocr_used": False}]
        pages: list[dict] = []
        current: list[dict] = []
        current_length = 0
        for block in blocks:
            if block.get("type") == "page_break":
                if current:
                    pages.append(FileService._page_from_blocks(len(pages) + 1, current))
                    current, current_length = [], 0
                continue
            block_length = len(str(block.get("text", "")))
            if current and current_length + block_length > settings.document_page_characters:
                pages.append(FileService._page_from_blocks(len(pages) + 1, current))
                current, current_length = [], 0
            current.append(block)
            current_length += block_length + 1
        if current:
            pages.append(FileService._page_from_blocks(len(pages) + 1, current))
        return pages

    @staticmethod
    def _page_from_blocks(page_number: int, blocks: list[dict]) -> dict:
        return {
            "page_number": page_number,
            "text": "\n".join(str(block.get("text", "")) for block in blocks),
            "blocks": blocks,
            "ocr_used": False,
            "text_source": "native",
        }

    @staticmethod
    def _mime_type(extension: str) -> str:
        explicit = {
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "txt": "text/plain",
        }
        return explicit.get(extension, mimetypes.types_map.get(f".{extension}", "application/octet-stream"))

    @staticmethod
    def _soffice_path() -> str | None:
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if executable:
            return executable
        macos_path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
        return str(macos_path) if macos_path.is_file() else None

    @classmethod
    def _preview_available(cls, extension: str) -> bool:
        return extension == "pdf" or bool(cls._soffice_path())

    @classmethod
    def _convert_office_to_pdf(cls, path: Path) -> Path | None:
        soffice = cls._soffice_path()
        if not soffice:
            return None
        preview = path.with_name(f"{path.stem}-preview.pdf")
        if (
            preview.is_file()
            and preview.stat().st_mtime >= path.stat().st_mtime
            and cls._office_preview_is_usable(preview)
        ):
            return preview
        with tempfile.TemporaryDirectory(prefix="contract-upload-preview-") as temp_dir:
            converted = cls._run_office_conversion(path, Path(temp_dir), soffice)
            if not converted or not cls._office_preview_is_usable(converted):
                return None
            shutil.copyfile(converted, preview)
        return preview

    @classmethod
    def _run_office_conversion(
        cls, path: Path, output_dir: Path, soffice: str | None = None
    ) -> Path | None:
        executable = soffice or cls._soffice_path()
        if not executable:
            return None
        profile_dir = output_dir / "libreoffice-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        environment = cls._office_conversion_environment(output_dir, executable)
        result = subprocess.run(
            [
                executable,
                f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(path),
            ],
            capture_output=True,
            check=False,
            timeout=120,
            env=environment,
        )
        converted = output_dir / f"{path.stem}.pdf"
        return converted if result.returncode == 0 and converted.is_file() else None

    @staticmethod
    def _office_conversion_environment(output_dir: Path, soffice: str) -> dict[str, str]:
        environment = os.environ.copy()
        cache_dir = output_dir / "font-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        environment["XDG_CACHE_HOME"] = str(cache_dir)
        if sys.platform != "darwin":
            return environment

        resources_fonts = (
            Path(soffice).resolve().parent.parent / "Resources" / "fonts" / "truetype"
        )
        font_dirs = [
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
            resources_fonts,
        ]
        configured_dirs = [item for item in font_dirs if item.is_dir()]
        font_config = output_dir / "fonts.conf"
        directory_xml = "\n".join(
            f"  <dir>{escape(str(item))}</dir>" for item in configured_dirs
        )
        font_config.write_text(
            (
                '<?xml version="1.0"?>\n'
                '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
                "<fontconfig>\n"
                f"{directory_xml}\n"
                '  <cachedir prefix="xdg">fontconfig</cachedir>\n'
                "</fontconfig>\n"
            ),
            encoding="utf-8",
        )
        environment["FONTCONFIG_FILE"] = str(font_config)
        return environment

    @classmethod
    def _office_pages(cls, blocks: list[dict], preview: Path | None) -> list[dict]:
        logical_pages = cls._paginate_blocks(blocks)
        if not preview:
            return logical_pages
        try:
            physical_texts = [cls._extract_pdf_text(page) for page in PdfReader(preview).pages]
        except Exception:
            return logical_pages
        if not physical_texts:
            return logical_pages

        page_blocks: list[list[dict]] = [[] for _ in physical_texts]
        normalized_pages = [cls._normalize_match_text(text) for text in physical_texts]
        current_page = 0
        matched_anchors = 0
        for block in blocks:
            if block.get("type") == "page_break":
                current_page = min(current_page + 1, len(page_blocks) - 1)
                continue
            block_text = cls._normalize_match_text(str(block.get("text", "")))
            anchors = cls._block_match_anchors(block_text)
            if anchors:
                matched_page = next(
                    (
                        index
                        for index in range(current_page, len(normalized_pages))
                        if any(anchor in normalized_pages[index] for anchor in anchors)
                    ),
                    None,
                )
                if matched_page is not None:
                    current_page = matched_page
                    matched_anchors += 1
            page_blocks[current_page].append(block)
        if not matched_anchors and not any(
            block.get("type") == "page_break" for block in blocks
        ):
            return cls._distribute_blocks_by_physical_pages(blocks, physical_texts)
        pages = [
            cls._page_from_blocks(
                index,
                assigned or cls._text_blocks(physical_texts[index - 1]),
            )
            for index, assigned in enumerate(page_blocks, start=1)
        ]
        return pages if any(page["blocks"] for page in pages) else logical_pages

    @classmethod
    def _office_preview_is_usable(cls, preview: Path | None) -> bool:
        if not preview or not preview.is_file():
            return False
        try:
            texts = [cls._extract_pdf_text(page) for page in PdfReader(preview).pages]
        except Exception:
            return False
        return bool(texts) and all(text.strip() and cls._text_is_usable(text) for text in texts)

    @staticmethod
    def _parse_txt(path: Path) -> str:
        raw = path.read_bytes()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            return raw.decode("utf-16")
        if raw.count(b"\x00") > max(2, len(raw) // 10):
            odd_nuls = raw[1::2].count(0)
            even_nuls = raw[::2].count(0)
            encoding = "utf-16-le" if odd_nuls >= even_nuls else "utf-16-be"
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                pass
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise FileParseError(
            f"文件“{path.name}”编码无法识别，请使用 UTF-8、UTF-16 或 GB18030。"
        )

    @staticmethod
    def _parse_doc(path: Path) -> str:
        textutil = Path("/usr/bin/textutil")
        if textutil.exists():
            command = [
                str(textutil),
                "-convert",
                "txt",
                "-encoding",
                "UTF-8",
                "-stdout",
                str(path),
            ]
        elif antiword := shutil.which("antiword"):
            command = [antiword, str(path)]
        else:
            raise FileParseError("当前环境暂不支持旧版 DOC 解析，请转换为 DOCX 后重试。")
        result = subprocess.run(command, capture_output=True, check=False, timeout=30)
        if result.returncode != 0:
            raise FileParseError(f"文件“{path.name}”解析失败，请转换为 DOCX 后重试。")
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return result.stdout.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise FileParseError(f"文件“{path.name}”文本编码无法识别，请转换为 DOCX 后重试。")

    @staticmethod
    def _extract_pdf_text(page) -> str:
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except (KeyError, TypeError, ValueError):
            try:
                text = page.extract_text() or ""
            except KeyError:
                text = ""
        return text.replace("\x00", "").strip()

    @staticmethod
    def _text_is_usable(text: str) -> bool:
        if not text.strip() or "\ufffd" in text or "锟斤拷" in text:
            return False
        visible = sum(character.isprintable() or character in "\n\r\t" for character in text)
        if visible / max(1, len(text)) < 0.97:
            return False
        cjk = [character for character in text if "\u4e00" <= character <= "\u9fff"]
        if len(cjk) >= 20:
            dominant_count = max(cjk.count(character) for character in set(cjk))
            if dominant_count / len(cjk) > 0.35:
                return False
        return True

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        return "".join(value.split())

    @staticmethod
    def _block_match_anchors(block_text: str) -> list[str]:
        anchors = [block_text[: min(28, len(block_text))]] if block_text else []
        ascii_tokens: list[str] = []
        token = ""
        for character in block_text:
            if character.isascii() and (character.isalnum() or character in ".,%/-"):
                token += character
            else:
                if len(token) >= 4:
                    ascii_tokens.append(token)
                token = ""
        if len(token) >= 4:
            ascii_tokens.append(token)
        anchors.extend(sorted(set(ascii_tokens), key=len, reverse=True)[:3])
        return [anchor for anchor in anchors if anchor]

    @classmethod
    def _distribute_blocks_by_physical_pages(
        cls, blocks: list[dict], physical_texts: list[str]
    ) -> list[dict]:
        content_blocks = [block for block in blocks if block.get("type") != "page_break"]
        if not content_blocks:
            return [cls._page_from_blocks(index, []) for index in range(1, len(physical_texts) + 1)]
        weights = [max(1, len(cls._normalize_match_text(text))) for text in physical_texts]
        total_weight = sum(weights)
        total_length = sum(max(1, len(str(block.get("text", "")))) for block in content_blocks)
        boundaries: list[float] = []
        cumulative_weight = 0
        for weight in weights[:-1]:
            cumulative_weight += weight
            boundaries.append(total_length * cumulative_weight / total_weight)

        page_blocks: list[list[dict]] = [[] for _ in physical_texts]
        page_index = 0
        consumed = 0
        for block in content_blocks:
            block_length = max(1, len(str(block.get("text", ""))))
            midpoint = consumed + block_length / 2
            while page_index < len(boundaries) and midpoint > boundaries[page_index]:
                page_index += 1
            page_blocks[page_index].append(block)
            consumed += block_length
        return [
            cls._page_from_blocks(index, assigned)
            for index, assigned in enumerate(page_blocks, start=1)
        ]


class OcrUnavailableError(RuntimeError):
    pass


class OcrProcessingError(RuntimeError):
    pass
