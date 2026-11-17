from fastapi import APIRouter, Depends
from app.dependencies import get_database
from app.schemas import UserResponse

router = APIRouter(tags=["Demo users"])


@router.get("/users", response_model=list[UserResponse])
def list_users(db=Depends(get_database, scope="function")):
    return [dict(row) for row in db.execute("SELECT * FROM users ORDER BY id")]
