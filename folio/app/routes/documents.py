from fastapi import APIRouter, Depends, Response, UploadFile
from app.dependencies import get_current_user, get_database
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentSummary
from app.services import documents
from app.services.imports import read_text_file

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=list[DocumentSummary])
def list_documents(user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    return documents.list_documents(db, user["id"])


@router.post("", status_code=201, response_model=DocumentResponse)
def create_document(data: DocumentCreate, response: Response,
                    user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    document = documents.create_document(db, data, user["id"])
    response.headers["Location"] = f"/api/documents/{document['id']}"
    return document


@router.post("/import", status_code=201, response_model=DocumentResponse)
def import_document(file: UploadFile, response: Response,
                    user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    try:
        document = documents.create_document(db, read_text_file(file), user["id"])
        response.headers["Location"] = f"/api/documents/{document['id']}"
        return document
    finally:
        file.file.close()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    return documents.get_document(db, document_id, user["id"])


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: int, data: DocumentUpdate,
                    user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    return documents.update_document(db, document_id, data, user["id"])
