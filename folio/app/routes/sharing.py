from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, get_database
from app.schemas import ShareCreate, UserResponse
from app.services import sharing

router = APIRouter(prefix="/documents/{document_id}/shares", tags=["Sharing"])


@router.get("", response_model=list[UserResponse])
def list_shares(document_id: int, user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    return sharing.list_shares(db, document_id, user["id"])


@router.post("", status_code=201)
def share_document(document_id: int, data: ShareCreate,
                   user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    sharing.grant_access(db, document_id, user["id"], data.user_id)
    return {"message": "Editor access granted."}


@router.delete("/{user_id}", status_code=204)
def remove_share(document_id: int, user_id: int,
                 user=Depends(get_current_user), db=Depends(get_database, scope="function")):
    sharing.remove_access(db, document_id, user["id"], user_id)
