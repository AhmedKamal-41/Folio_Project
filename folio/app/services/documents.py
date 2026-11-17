import json
from fastapi import HTTPException


def get_accessible_document(db, document_id, user_id, owner_only=False):
    document = db.execute("""
        SELECT d.*, u.name AS owner_name FROM documents d
        JOIN users u ON u.id = d.owner_id
        WHERE d.id = ? AND (d.owner_id = ? OR EXISTS (
            SELECT 1 FROM shares s WHERE s.document_id = d.id AND s.user_id = ?
        ))
    """, (document_id, user_id, user_id)).fetchone()
    if document is None:
        raise HTTPException(404, "Document not found or access was removed.")
    if owner_only and document["owner_id"] != user_id:
        raise HTTPException(403, "Only the owner can manage sharing.")
    return document



def serialize_document(document):
    result = dict(document)
    result["content"] = json.loads(result["content"])
    return result



def list_documents(db, user_id):
    rows = db.execute("""
        SELECT d.id, d.title, d.owner_id, u.name AS owner_name, d.updated_at, d.version
        FROM documents d JOIN users u ON u.id = d.owner_id
        WHERE d.owner_id = ? OR EXISTS (
            SELECT 1 FROM shares s WHERE s.document_id = d.id AND s.user_id = ?
        ) ORDER BY d.updated_at DESC, d.id DESC
    """, (user_id, user_id))
    return [dict(row) for row in rows]


def create_document(db, data, user_id):
    cursor = db.execute("INSERT INTO documents (owner_id, title, content) VALUES (?, ?, ?)",
                        (user_id, data.title, json.dumps(data.content)))
    return get_document(db, cursor.lastrowid, user_id)


def get_document(db, document_id, user_id):
    return serialize_document(get_accessible_document(db, document_id, user_id))


def update_document(db, document_id, data, user_id):
    get_accessible_document(db, document_id, user_id)
    cursor = db.execute("""
        UPDATE documents SET title = ?, content = ?, version = version + 1,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND version = ? AND (owner_id = ? OR EXISTS (
            SELECT 1 FROM shares WHERE document_id = documents.id AND user_id = ?
        ))
    """, (data.title, json.dumps(data.content), document_id, data.version, user_id, user_id))
    if cursor.rowcount == 0:
        get_accessible_document(db, document_id, user_id)
        raise HTTPException(409, "Another user saved changes. Download your draft, then reload the latest version.")
    return get_document(db, document_id, user_id)
