from pydantic import BaseModel


class ParsedFile(BaseModel):
    file_name: str
    file_extension: str
    mime_type: str
    character_count: int
    page_count: int
    ocr_used: bool
    ocr_status: str
    ocr_message: str | None = None
    text_source: str
    preview_available: bool


class ContractUploadResponse(BaseModel):
    upload_id: str
    main_file: ParsedFile
    attachments: list[ParsedFile]
