from fastapi import Depends, Header, HTTPException, Request
from app.database import database


def get_database(request: Request):
    with database(request.app.state.settings.database_path) as db:
        yield db


def get_current_user(x_user_id: int = Header(...), db=Depends(get_database, scope="function")):
    user = db.execute("SELECT * FROM users WHERE id = ?", (x_user_id,)).fetchone()
    if user is None:
        raise HTTPException(401, "Select a valid demo account.")
    return dict(user)
