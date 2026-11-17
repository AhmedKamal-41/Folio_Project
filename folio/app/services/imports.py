from pathlib import Path
from fastapi import HTTPException
from app.config import MAX_UPLOAD_BYTES, MAX_CONTENT_CHARACTERS
from app.schemas import DocumentCreate


def read_text_file(file):
    filename = Path((file.filename or "").replace("\\", "/")).name
    if Path(filename).suffix.lower() != ".txt":
        raise HTTPException(400, "Choose a UTF-8 .txt file (maximum 1 MB).")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the 1 MB limit.")
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise HTTPException(400, "The file must use UTF-8 text encoding.")
    if not text.strip() or "\x00" in text or len(text) > (MAX_CONTENT_CHARACTERS - 1):
        raise HTTPException(400, "Use nonempty text without null bytes, under 100,000 characters.")
    data = DocumentCreate(title=Path(filename).stem.strip()[:120] or "Imported document",
                         content={"ops": [{"insert": text.rstrip("\n") + "\n"}]})
    return data
