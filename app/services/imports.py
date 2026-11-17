from io import BytesIO
from pathlib import Path
from docx import Document as WordDocument
from fastapi import HTTPException
from app.config import MAX_UPLOAD_BYTES, MAX_CONTENT_CHARACTERS, MAX_CONTENT_OPERATIONS
from app.schemas import DocumentCreate

HEADING_STYLES = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3}
LIST_STYLES = {"List Bullet": "bullet", "List Bullet 2": "bullet", "List Bullet 3": "bullet",
              "List Number": "ordered", "List Number 2": "ordered", "List Number 3": "ordered"}


def read_import_file(file):
    filename = Path((file.filename or "").replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    if extension not in (".txt", ".docx"):
        raise HTTPException(400, "Choose a UTF-8 .txt or Word (.docx) file (maximum 1 MB).")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the 1 MB limit.")
    ops = read_docx_ops(raw) if extension == ".docx" else read_text_ops(raw)
    title = Path(filename).stem.strip()[:120] or "Imported document"
    return DocumentCreate(title=title, content={"ops": ops})


def read_text_ops(raw):
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise HTTPException(400, "The file must use UTF-8 text encoding.")
    if not text.strip() or "\x00" in text or len(text) > (MAX_CONTENT_CHARACTERS - 1):
        raise HTTPException(400, "Use nonempty text without null bytes, under 100,000 characters.")
    return [{"insert": text.rstrip("\n") + "\n"}]


def read_docx_ops(raw):
    try:
        document = WordDocument(BytesIO(raw))
    except Exception:
        raise HTTPException(400, "Could not read this Word document.")
    ops = []
    length = 0
    for paragraph in document.paragraphs:
        style_name = paragraph.style.name if paragraph.style else ""
        for run in paragraph.runs:
            text = run.text.replace("\x00", "")
            if not text:
                continue
            length += len(text)
            attributes = {name: True for name, active in
                         (("bold", run.bold), ("italic", run.italic), ("underline", run.underline)) if active}
            ops.append({"insert": text, "attributes": attributes} if attributes else {"insert": text})
        newline = {"insert": "\n"}
        if style_name in HEADING_STYLES:
            newline["attributes"] = {"header": HEADING_STYLES[style_name]}
        elif style_name in LIST_STYLES:
            newline["attributes"] = {"list": LIST_STYLES[style_name]}
        ops.append(newline)
        length += 1
        if length > MAX_CONTENT_CHARACTERS:
            raise HTTPException(400, "Document exceeds the 100,000 character limit.")
    if len(ops) > MAX_CONTENT_OPERATIONS:
        raise HTTPException(400, "Document exceeds 5,000 formatted sections.")
    if not any(op["insert"].strip() for op in ops):
        raise HTTPException(400, "The document has no readable text.")
    return ops
