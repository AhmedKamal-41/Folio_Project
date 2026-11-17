from fastapi import APIRouter, Depends
from app.dependencies import get_database

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(db=Depends(get_database, scope="function")):
    db.execute("SELECT 1 FROM users LIMIT 1")
    return {"status": "ok"}
