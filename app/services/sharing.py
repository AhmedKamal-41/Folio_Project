from fastapi import HTTPException
from app.services.documents import get_accessible_document


def list_shares(db, document_id, owner_id):
    get_accessible_document(db, document_id, owner_id, owner_only=True)
    rows = db.execute("""
        SELECT u.* FROM shares s JOIN users u ON u.id = s.user_id
        WHERE s.document_id = ? ORDER BY u.id
    """, (document_id,))
    return [dict(row) for row in rows]


def grant_access(db, document_id, owner_id, recipient_id):
    document = get_accessible_document(db, document_id, owner_id, owner_only=True)
    if recipient_id == document["owner_id"]:
        raise HTTPException(400, "The owner already has access.")
    if db.execute("SELECT id FROM users WHERE id = ?", (recipient_id,)).fetchone() is None:
        raise HTTPException(404, "User not found.")
    db.execute("INSERT OR IGNORE INTO shares VALUES (?, ?)", (document_id, recipient_id))


def remove_access(db, document_id, owner_id, recipient_id):
    get_accessible_document(db, document_id, owner_id, owner_only=True)
    db.execute("DELETE FROM shares WHERE document_id = ? AND user_id = ?", (document_id, recipient_id))
