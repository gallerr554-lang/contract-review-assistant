from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.contract import ContractUploadResponse, ParsedFile
from app.core.dependencies import CurrentUser
from app.service.file_service import FileParseError, FileService

router = APIRouter()


@router.post("/upload", response_model=ContractUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    main_file: Annotated[UploadFile, File(...)],
    user: CurrentUser,
    attachments: Annotated[list[UploadFile] | None, File()] = None,
) -> ContractUploadResponse:
    try:
        manifest = await FileService().save_and_parse(main_file, attachments or [], user.id)
    except FileParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return ContractUploadResponse(
        upload_id=manifest["upload_id"],
        main_file=ParsedFile(**manifest["main_file"]),
        attachments=[ParsedFile(**item) for item in manifest["attachments"]],
    )
