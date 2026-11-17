import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def initialize_database(path):
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with database(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(schema)
        db.executemany("INSERT OR IGNORE INTO users (id, name, email) VALUES (?, ?, ?)", [
            (1, "Ahmed Ali", "ahmed@example.com"),
            (2, "Sara Chen", "sara@example.com"),
            (3, "Omar Hassan", "omar@example.com"),
        ])
