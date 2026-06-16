"""Routes for EPUB parsing."""
import os
import tempfile

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException

from ..auth import require_api_key
from ..deps import get_epub_reader, get_settings
from ..schemas import ParseEpubResponse
from ....application.services import ParseEpubService
from ....infrastructure.adapters.epub_reader import extract_cover

router = APIRouter(prefix="/api/epub", tags=["epub"])


@router.post("/parse", response_model=ParseEpubResponse, dependencies=[Depends(require_api_key)])
async def parse_epub(file: UploadFile = File(...)) -> ParseEpubResponse:
    """Upload an EPUB and receive the extracted editable TXT content."""
    if not file.filename or not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are accepted")

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        service = ParseEpubService(get_epub_reader())
        txt_content, title, author = service.from_file(tmp_path)
        covers_dir = os.path.join(get_settings().output_dir, ".covers")
        cover_path = extract_cover(tmp_path, covers_dir)
    finally:
        os.unlink(tmp_path)

    return ParseEpubResponse(
        txt_content=txt_content,
        book_title=title,
        book_author=author,
        cover_path=cover_path,
    )
