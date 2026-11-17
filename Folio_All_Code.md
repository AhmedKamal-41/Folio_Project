# Folio — modular project source

Each FILE marker identifies a separate file in the project. Use the ZIP for the ready-to-run folder structure.
Quill third-party assets are bundled in the ZIP; run `python download_vendor.py` if reconstructing from this text.

````text

======================================================================
FILE: main.py
======================================================================
from app.application import create_app

app = create_app()

======================================================================
FILE: app/application.py
======================================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import MAX_REQUEST_BYTES, STATIC_DIR, load_settings
from app.database import initialize_database
from app.middleware import RequestSizeLimit, security_headers
from app.routes import documents, health, sharing, users


def create_app(database_path=None):
    settings = load_settings(database_path)

    @asynccontextmanager
    async def lifespan(application):
        initialize_database(settings.database_path)
        yield

    application = FastAPI(title="Folio", version="1.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(RequestSizeLimit, max_bytes=MAX_REQUEST_BYTES)
    application.middleware("http")(security_headers)
    for router in (health.router, users.router, documents.router, sharing.router):
        application.include_router(router, prefix="/api")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application

======================================================================
FILE: app/config.py
======================================================================
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_DIR / "static"
MAX_UPLOAD_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 2 * MAX_UPLOAD_BYTES
MAX_CONTENT_CHARACTERS = 100000
MAX_CONTENT_OPERATIONS = 5000


@dataclass(frozen=True)
class Settings:
    database_path: Path


def load_settings(database_path=None):
    path = database_path or os.getenv("DATABASE_PATH", PROJECT_DIR / "data" / "folio.db")
    return Settings(database_path=Path(path))

======================================================================
FILE: app/database.py
======================================================================
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

======================================================================
FILE: app/schema.sql
======================================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL, content TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS shares (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id), PRIMARY KEY (document_id, user_id)
);

CREATE INDEX IF NOT EXISTS documents_owner_index ON documents(owner_id);
CREATE INDEX IF NOT EXISTS shares_user_index ON shares(user_id);

======================================================================
FILE: app/dependencies.py
======================================================================
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

======================================================================
FILE: app/schemas.py
======================================================================
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.config import MAX_CONTENT_CHARACTERS, MAX_CONTENT_OPERATIONS


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled document", max_length=120)
    content: dict = Field(default_factory=lambda: {"ops": [{"insert": "\n"}]})

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        ops = value.get("ops")
        if set(value) != {"ops"} or not isinstance(ops, list) or not 1 <= len(ops) <= MAX_CONTENT_OPERATIONS:
            raise ValueError("Content must contain between 1 and 5,000 text operations.")
        length = 0
        for operation in ops:
            if not isinstance(operation, dict) or set(operation) - {"insert", "attributes"}:
                raise ValueError("Invalid text operation.")
            if not isinstance(operation.get("insert"), str):
                raise ValueError("Only text content is supported.")
            length += len(operation["insert"])
            attributes = operation.get("attributes", {})
            if not isinstance(attributes, dict):
                raise ValueError("Invalid formatting.")
            for name, setting in attributes.items():
                if name in ("bold", "italic", "underline") and type(setting) is bool:
                    continue
                if name == "header" and type(setting) is int and setting in (1, 2, 3):
                    continue
                if name == "list" and isinstance(setting, str) and setting in ("bullet", "ordered"):
                    continue
                raise ValueError("Unsupported formatting.")
        if length > MAX_CONTENT_CHARACTERS or not ops[-1]["insert"].endswith("\n"):
            raise ValueError("Content must end with a newline and fit within 100,000 characters.")
        return value



class DocumentUpdate(DocumentCreate):
    version: int = Field(ge=1)



class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=1)



class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class DocumentSummary(BaseModel):
    id: int
    title: str
    owner_id: int
    owner_name: str
    version: int
    updated_at: str


class DocumentResponse(DocumentSummary):
    content: dict

======================================================================
FILE: app/middleware.py
======================================================================
from collections import deque


async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response



class RequestSizeLimit:
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        messages = deque()
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json")]})
                return await send({"type": "http.response.body",
                                   "body": b'{"detail":"Request is too large."}'})
            messages.append(message)
            if not message.get("more_body", False):
                break
        async def replay():
            if messages:
                return messages.popleft()
            return await receive()
        await self.app(scope, replay, send)

======================================================================
FILE: .dockerignore
======================================================================
.venv
__pycache__
data
.git
node_modules
test-results
playwright-report
**/__pycache__
**/*.pyc

======================================================================
FILE: .github/workflows/tests.yml
======================================================================
name: Test Folio
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: python -m pip install -r requirements.txt
      - run: python -m unittest discover -s tests -v
      - run: npm ci --ignore-scripts
      - run: npm test

======================================================================
FILE: .gitignore
======================================================================
.venv/
__pycache__/
data/
.env
node_modules/
test-results/
playwright-report/

======================================================================
FILE: AI_WORKFLOW.md
======================================================================
# AI workflow note

Tool used: ChatGPT / Codex for implementation, review, documentation, and tests.
The assistant reviewed my Python solutions to use clear names, explicit control
flow, and focused functions as a reference for the coding style.

## Human direction

I asked for the code to be separated into professional, understandable files
while keeping a straightforward coding style. The refactor follows that
instruction: routes, services, schemas, persistence, and browser features have
separate responsibilities. I will review and run the final code before submission.

## Where AI helped

AI translated the requirements into a bounded create/edit/import/share flow,
implemented the API and browser code, separated the original larger files,
and generated tests and written setup/architecture notes.

## Output changed or rejected

- Replaced the all-in-one backend with a small application entry point and
  feature modules. Split frontend API, autosave, documents, sharing, and rendering.
- Fixed a document-list bug where a variable named `document` shadowed the
  browser DOM object. A rendering regression test now covers populated lists.
- Added an application factory for isolated test databases and ensured a
  successful response is sent after transaction commit.
- Kept version-checked saves and added tests for simultaneous writes and typing
  during a pending save. Added a plain-text draft download for conflict recovery.
- Chose Quill/Delta instead of hand-written rich-text commands/raw HTML storage.
- Kept real auth, live merging, comments, and DOCX support outside the timebox.

## Verification and remaining work

Backend tests exercise the actual HTTP application with temporary databases.
Frontend tests exercise save races and DOM rendering using LinkeDOM. They are
not a substitute for browser verification of the Quill toolbar and layout.
See `VALIDATION.md` for exact counts and what was actually run.

A local Chromium launch was unavailable earlier. Live deployment, real-browser
checks, recording, and the Google Drive submission are still pending. I will
only claim these after completing them and will explain the changes I personally
reviewed in my walkthrough.

======================================================================
FILE: ARCHITECTURE.md
======================================================================
# Architecture and prioritization

The product slice is a small workspace for creating, formatting, importing,
saving, and explicitly sharing documents with another demo user.

## Backend

`main.py` is a three-line entry point. `app/application.py` assembles FastAPI,
loads configuration, registers feature routers, and serves the frontend.

Routes handle HTTP input and output. Pydantic schemas validate requests and
define response contracts. Services contain document, permission, import, and
sharing logic. `database.py` owns connection and transaction lifetime;
`schema.sql` owns the tables and indexes. There is no extra repository,
controller, or abstract factory layer between these small components.

An application factory accepts a database path, allowing tests and multiple
app instances to use separate databases without patching a global variable.
Each request receives a connection. Its transaction commits before a success
response is sent and rolls back on failure. SQLite WAL mode is enabled.

All queries bind parameters. Document saves check the expected version and
current access in the SQL update. Only the owner can manage sharing. Demo
identity is a selected user ID, not a production authentication boundary.

## Frontend

Browser ES modules separate API requests, editor setup, UI rendering,
autosave, document workflows, and sharing. `app.js` connects their events.
The save manager is independent of the DOM and accepts small callbacks,
allowing meaningful tests of concurrent typing and in-flight requests.

The editor uses Quill. Validated Delta JSON preserves text and the supported
formatting. Embeds, links, unsupported attributes, and arbitrary operations
are rejected by the backend. Titles are inserted through `textContent`.

API calls have a 15-second timeout. Navigation waits for saves. HTTP 409
keeps the unsaved draft and pauses retries; a text download provides a way to
keep the draft before reloading. The application does not merge changes live.

## Infrastructure

One Python service serves both frontend and backend from one origin. No Node
build or third-party service is required at runtime. The Dockerfile copies
only runtime source and assets and uses `exec` for proper shutdown signals.
Docker Compose and Railway use a persistent `/data` volume. SQLite requires
this deployment to remain a single replica; it is not a distributed database.

## Scope cuts and next work

Real login, live merging, comments, history, DOCX import, and advanced sharing
roles remain outside this product slice. Every share grants editor access.
The text download protects conflict recovery; it is not a rich-document export.

Next: finish real-browser and deployed-persistence checks, record the video,
then add recovery drafts and a conflict comparison UI. Proper authentication
and a managed database would come before using the app for sensitive team data.

## Design references

- FastAPI routers: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Dependency cleanup before response: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- SQLite behavior: https://docs.python.org/3.12/library/sqlite3.html

======================================================================
FILE: DEPLOYMENT.md
======================================================================
# Deploy Folio on Railway

This file describes deployment steps. It does not claim a live deployment.

## 1. Push the source

Create a GitHub repository and push this directory with `main.py`, `app/`,
`static/`, requirements, Dockerfile, and Railway configuration at the root.
Exclude local databases, virtual environments, and `node_modules/`.

The GitHub Actions workflow runs backend and frontend tests on pushes and PRs.
The runtime itself does not use Node; `package.json` exists for test tooling.

## 2. Configure one Railway service

Create or reuse a project and service. Connect the repository's `main` branch.
Use the supplied root Dockerfile. Keep one service replica and one region.
There is no separate frontend hosting setup or CORS configuration to add.

## 3. Attach persistent storage

Attach a persistent volume to the application service at **`/data`**.
Set **`DATABASE_PATH=/data/folio.db`**. The Dockerfile already has this default.
The database initializes on first startup; no manual seed command is required.
Do not remove the volume or replace it with ephemeral container storage.

## 4. Publish and check

Generate a Railway public domain. The start command reads Railway's `PORT`.
Set the healthcheck path to **`/api/health`**, supplied in `railway.json`.
Wait for the deployment to finish successfully, then open the public URL.
Reviewers need no subscription, account registration, or password to use the demo.

## 5. Verify the real application

- Open `/api/health` and confirm `{"status":"ok"}`.
- Create, rename, and format a document; refresh and reopen it.
- Grant Sara access, switch accounts, and save a teammate edit.
- Check Omar cannot access it. Revoke Sara and check access again.
- Import the sample `.txt` file; reject an unsupported file.
- Open two tabs and demonstrate stale-save detection.
- Test **Download draft** before discarding a conflict.
- Test a narrow mobile screen and keyboard controls.
- Redeploy once and verify the same documents and shares still exist.

Only then update `DEPLOYMENT_URL.txt`, `VALIDATION.md`, and `SUBMISSION.md`.
Record the walkthrough and update `VIDEO_URL.txt`.

## Local deployment rehearsal

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Compose uses a persistent named volume and an HTTP
healthcheck. This project has not had a Docker image build verified in the
assistant environment; the Docker commands are provided for local verification.

## Troubleshooting

| Symptom | Check |
|---|---|
| Build looks for a Node start script | Select the supplied Dockerfile as the build path. |
| App cannot open its database | Confirm the `/data` volume and writable database path. |
| Documents disappear after redeploy | Confirm the service is using the attached persistent volume. |
| App is up but the domain fails | Check the app's `PORT` and generated domain target port. |
| Old edits return 409 | Download the draft, reload the saved document, and reapply changes. |

The demo intentionally allows switching identities. Use only demonstration
data. A production deployment for real team data needs actual authentication.

======================================================================
FILE: DEPLOYMENT_URL.txt
======================================================================
PENDING: Deploy the app with a persistent /data volume, verify it, and replace this line with the live URL.

======================================================================
FILE: Dockerfile
======================================================================
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY app ./app
COPY static ./static
ENV DATABASE_PATH=/data/folio.db PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

======================================================================
FILE: FILE_GUIDE.md
======================================================================
# Read the project step by step

`main.py` now only imports the application factory and creates the app.
Features are grouped by responsibility. The coding style stays procedural:
clear names, explicit conditions, normal SQL, and focused functions.

## Suggested reading order

1. **README.md**: run the app and try the reviewer flow.
2. **main.py** and **app/application.py**: understand startup and router registration.
3. **app/schema.sql** and **app/database.py**: see the data and transaction handling.
4. **app/schemas.py**: see what each API accepts and returns.
5. **app/routes/documents.py** and **app/services/documents.py**: follow creating and saving.
6. **app/dependencies.py** and the sharing files: follow identity and access checks.
7. **app/services/imports.py**: follow file validation and text conversion.
8. **static/index.html** and **static/js/app.js**: see the page and event connections.
9. **static/js/documents.js**, **autosave.js**, and **sharing.js**: follow browser workflows.
10. **tests/**, **DEPLOYMENT.md**, and **Dockerfile**: verify and deploy.

## Backend files

| File | What it does |
|---|---|
| `main.py` | Entry point used by `uvicorn main:app`. |
| `app/application.py` | Creates FastAPI, initializes the database at startup, and connects components. |
| `app/config.py` | Holds paths, upload/content limits, and database configuration. |
| `app/schema.sql` | Defines users, documents, shares, and query indexes. |
| `app/database.py` | Opens and closes SQLite connections; commits successful requests and rolls back failures. |
| `app/dependencies.py` | Supplies the request's connection and selected demo user. |
| `app/schemas.py` | Validates titles, rich-text operations, versions, and share requests; defines API responses. |
| `app/middleware.py` | Limits request sizes and adds security/cache headers. |
| `app/routes/documents.py` | Receives list/create/import/get/update requests and calls document services. |
| `app/routes/sharing.py` | Receives grant/list/revoke sharing requests. |
| `app/routes/users.py` | Lists the three demo users. |
| `app/routes/health.py` | Checks database availability for hosting readiness. |
| `app/services/documents.py` | Reads/writes documents, checks access, and detects stale saves. |
| `app/services/sharing.py` | Enforces owner-only sharing and grants or revokes editor access. |
| `app/services/imports.py` | Validates UTF-8 text files and turns them into a document payload. |

Package `__init__.py` files mark Python packages; they contain no feature logic.

## Frontend files

| File | What it does |
|---|---|
| `static/index.html` | Defines page structure, buttons, editor toolbar, and sharing dialog. |
| `static/styles.css` | Defines appearance and responsive layouts. |
| `static/js/app.js` | Connects UI events to the editor, save manager, and feature controllers. |
| `static/js/state.js` | Holds current account, document list, selected document, and filters. |
| `static/js/api.js` | Makes HTTP requests, selects demo identity, handles timeouts and API errors. |
| `static/js/dom.js` | Provides element lookup and user notifications. |
| `static/js/editor.js` | Initializes Quill, updates word counts, and downloads text drafts. |
| `static/js/view.js` | Renders the document list, ownership labels, account controls, and save status. |
| `static/js/autosave.js` | Debounces and serializes saves, tracks newer edits, and stops on conflicts. |
| `static/js/documents.js` | Handles create/open/import/refresh/account switching and draft-safe navigation. |
| `static/js/sharing.js` | Renders sharing controls and grants or revokes access. |
| `static/vendor/` | Contains the pinned third-party editor distribution and its license. |

## Trace one save

Clicking Save in the HTML triggers `app.js`, which asks `autosave.js` to flush
pending changes. The save callback calls `api.js`, which sends a PUT request.
`routes/documents.py` receives it after schema validation and identity checks.
`services/documents.py` checks access and updates the matching database version.
The database dependency commits before the success response is sent. The
browser then updates its saved version and status.

## Other files

| File | What it does |
|---|---|
| `tests/test_app.py` | Tests the real API and temporary databases. |
| `tests/frontend/autosave.test.js` | Tests asynchronous saves and conflict/failure recovery. |
| `tests/frontend/view.test.js` | Tests real DOM rendering using LinkeDOM; does not launch a browser. |
| `requirements.txt` | Pins Python dependencies. |
| `package.json`, `package-lock.json` | Define and lock development-only frontend test dependencies. |
| `download_vendor.py` | Restores pinned Quill assets with checksum verification if needed. |
| `Dockerfile`, `compose.yaml`, `railway.json` | Build, run, persist, and healthcheck the app. |
| `DEPLOYMENT.md` | Explains deployment and post-deployment verification. |
| `ARCHITECTURE.md`, `AI_WORKFLOW.md`, `VALIDATION.md` | Explain design, AI usage, and verification evidence. |
| `WALKTHROUGH.md`, `SUBMISSION.md`, URL files | Prepare the assessment submission. |

The generated SQLite database is `data/folio.db` locally or `/data/folio.db`
in Docker/Railway. It is not committed to source or included in the ZIP.

======================================================================
FILE: README.md
======================================================================
# Folio

A focused document workspace: create, format, rename, save, import, and share.
Built with FastAPI, SQLite, vanilla JavaScript modules, and Quill 2.0.3.

## Run locally

Requires Python 3.12+. The application does not need Node, API keys, or a paid
editor service. Open a terminal in this directory.

```bash
python -m venv .venv
```

Activate the environment using the command for your operating system:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Then install and start:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000. The database and three demo accounts are created
on startup. Editor assets are already included in the ZIP. When reconstructing
from the combined code file, run `python download_vendor.py` first.

## Review the main flow

1. As **Ahmed Ali**, create and rename a document.
2. Add text and try bold, italic, underline, headings, and lists.
3. Wait for **All changes saved**, refresh, and reopen the document.
4. Select **Share**, grant **Sara Chen** access, and close the sharing window.
5. Switch to Sara: the document is marked **Shared with you**. Edit and save.
6. Switch back to Ahmed and reopen the document to see Sara's changes.
7. Switch to **Omar Hassan**: he has no access until the owner shares it.
8. As Ahmed, remove Sara's access in the sharing window.
9. Import `samples/team-notes.txt` and edit the imported document.

Use **Refresh document list** to retrieve newly shared or renamed documents.

The seeded accounts are Ahmed (ID 1), Sara (ID 2), and Omar (ID 3). No passwords.
The UI simulates identity through `X-User-Id`; anyone can switch accounts.
Permissions are checked by the server for the selected identity. This is demo
authentication allowed by the assignment, not a real login system.

## Project organization

| Location | Responsibility |
|---|---|
| `main.py` | Three-line application entry point. |
| `app/application.py` | Builds the app and registers routes, middleware, and static files. |
| `app/routes/` | HTTP endpoints grouped into documents, sharing, users, and health. |
| `app/services/` | Document operations, access rules, sharing, and text import. |
| `app/schemas.py` | Request validation and response models. |
| `app/database.py`, `app/schema.sql` | SQLite connections, transactions, tables, indexes, and demo accounts. |
| `app/dependencies.py`, `app/config.py` | Request-scoped database access, demo identity, paths, and limits. |
| `app/middleware.py` | Request-size limits and response headers. |
| `static/js/` | Separate modules for API calls, editor, autosave, documents, sharing, and rendering. |
| `tests/` | Backend workflows, autosave behavior, and DOM rendering tests. |
| `.github/workflows/tests.yml` | Runs Python and JavaScript tests on pushes and pull requests. |

Start with **FILE_GUIDE.md** for a suggested reading order and complete file map.

## Saving and conflicts

Title and content autosave after a 900 ms pause. Save and Ctrl/Cmd+S work too.
Saves are serialized. Typing during a save leaves the newer changes pending
until they are saved. Navigation waits for pending changes; failed saves keep
the current draft open. The page warns before leaving with unsaved changes.

A version check rejects stale saves with HTTP 409. The draft stays in the
editor. Use **Download draft** to save a plain-text copy before choosing
**Reload latest** and reapplying your edits. This download does not retain
rich formatting. Drafts are not backed up offline; keep the tab open until a
save succeeds or you have downloaded a copy.

To demonstrate a conflict, open the same saved document in two tabs. Save a
change in one, then edit and save the older copy in the other. There is no
live merging, live cursor sharing, or version-history feature.

## Import limits

UTF-8 `.txt` only, up to 1 MB and fewer than 100,000 characters. Empty files,
null bytes, invalid encodings, and other extensions are rejected. Uploaded
markup becomes plain editable text; original binary files are not retained.
Rich documents support up to 100,000 characters including the final newline
and up to 5,000 text operations. Full request bodies are limited to 2 MB.

## Tests

Backend tests require only the Python requirements:

```bash
python -m unittest discover -s tests -v
```

Frontend tests use Node 22+ and a development-only DOM library:

```bash
npm ci --ignore-scripts
npm test
```

The application itself has no Node build step. Tests cover owner/teammate
flows, permission revocation, formatting persistence, imports, simultaneous
saves, database isolation, durable responses, rendering, and autosave races.
See `VALIDATION.md` for what was actually verified and what remains unverified.

## Docker and Railway

Docker Compose builds and runs one application instance with durable data:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. The named volume retains the database between runs.
Do not remove the volume if you need to keep its documents.

For Railway, use the supplied Dockerfile, one replica, a volume mounted at
`/data`, and `DATABASE_PATH=/data/folio.db`. The app reads Railway's `PORT` and
serves the frontend and API together. Set the healthcheck to `/api/health`.
See **DEPLOYMENT.md** for the exact deployment and verification steps.

## Submission

No live URL or recording is claimed. Finish browser checks and deployment,
record the walkthrough using `WALKTHROUGH.md`, and update `DEPLOYMENT_URL.txt`,
`VIDEO_URL.txt`, and `SUBMISSION.md`. Put the source, notes, and video link in
one Google Drive folder with reviewer access.

## References

- FastAPI modular applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Quill editor: https://quilljs.com/docs/quickstart/
- Quill's BSD license is included under `static/vendor/QUILL-LICENSE.txt`.

======================================================================
FILE: SUBMISSION.md
======================================================================
# Folio — Ahmed Ali

Status: modular source implementation and automated verification complete.
Real-browser verification, live deployment, walkthrough, and Drive submission
are pending and must be completed before presenting this as a finished submission.

## Review links

- Google Drive folder: PENDING
- Live application: PENDING
- Walkthrough video: PENDING

## Included

- FastAPI backend separated into application setup, routes, services, schemas,
  dependencies, middleware, configuration, and SQLite persistence.
- Browser modules for API calls, rich-text editing, documents, sharing, autosave,
  and UI rendering.
- Create, rename, rich-text editing, autosave/manual save, and reopening.
- UTF-8 `.txt` import with documented limits and error handling.
- Owner-controlled editor access, owned/shared indicators, and revocation.
- Version-checked saves and plain-text draft download for conflict recovery.
- 12 backend and 13 frontend tests; GitHub Actions workflow included.
- README, file guide, architecture note, AI workflow note, validation note,
  deployment guide, Dockerfile, Compose file, Railway configuration, and video outline.
- Pinned Quill assets and BSD license; sample import file.

## Demo accounts

Select Ahmed Ali, Sara Chen, or Omar Hassan. No passwords or payment required.
Identity is simulated and can be changed by any reviewer. Follow the README
steps to demonstrate ownership, sharing, teammate edits, and revocation.

## Run locally

Python 3.12+. Create/activate a virtual environment, install `requirements.txt`,
and run `python -m uvicorn main:app --reload`. Open http://127.0.0.1:8000.
Node 22+ is only needed for optional frontend tests: `npm ci --ignore-scripts`
and `npm test`. Backend tests: `python -m unittest discover -s tests -v`.

## Incomplete and intentionally omitted

The live URL, recording URL, reviewer Drive link, real-browser checks, Docker
build, and deployed persistence checks are incomplete. URL files are placeholders.
Real login, live merging, comments, history, advanced permissions, DOCX import,
and rich-document export are outside this scope.

## Next 2–4 hours

Complete browser/deployment verification, record the walkthrough, and assemble
one Google Drive folder. Then improve draft recovery and conflict comparison.

## Final checklist

- [ ] Review and run the generated code yourself.
- [ ] Complete the browser and deployment checklist in DEPLOYMENT.md.
- [ ] Update VALIDATION.md with the actual results.
- [ ] Fill DEPLOYMENT_URL.txt and the live link above.
- [ ] Record/upload the walkthrough and fill VIDEO_URL.txt.
- [ ] Upload source and notes to one reviewer-accessible Google Drive folder.
- [ ] Replace every PENDING link with its actual URL.

======================================================================
FILE: VALIDATION.md
======================================================================
# Verification

Verified in this environment:

- 12 backend tests: `python -m unittest discover -s tests -v`.
- 13 frontend tests: `npm test` after installing the pinned development dependency.
- Python compilation and JavaScript syntax checks.
- API response models, documented endpoint groups, and module asset availability.
- Each pinned Python dependency version exists on PyPI.

## What the tests cover

Backend: create, formatted edits, save/reopen, sharing and teammate editing,
owner-only access management, revocation, text import failure modes, request
limits, stale and simultaneous writes, isolation between app instances,
persistence across startup, and transaction commit before HTTP success.

Frontend: document-list rendering, owned/shared labels, title escaping,
filters, owner-only controls, busy navigation, serialized saves, typing during
an in-flight request, conflict preservation, retrying failed saves, and title
validation. These tests use real DOM nodes through LinkeDOM for rendering and
controlled asynchronous callbacks for autosave.

## Not yet verified

- Actual Chromium/Firefox/Safari editor interactions and visual appearance.
- Keyboard formatting, mobile layout, and draft downloads in a real browser.
- Docker image build, Railway release, and persistence across deployed restarts.
- A recorded walkthrough and reviewer-accessible Drive folder.

The earlier local browser launch was blocked by the environment. A remote
browser could not reach the development server. No browser screenshots or
successful browser smoke test are claimed.

Use the real-application checklist in `DEPLOYMENT.md` before recording. Update
this note only after completing those checks.

======================================================================
FILE: VIDEO_URL.txt
======================================================================
PENDING: Record the 3–5 minute walkthrough, upload it with reviewer access, and replace this line with the video URL.

======================================================================
FILE: WALKTHROUGH.md
======================================================================
# Walkthrough recording outline — about 4 minutes

Record the real application in a browser. Explain these points in your own words.

## 0:00–0:25 — Scope

“This is Folio, a small workspace for creating and sharing documents. I focused
on the complete writing and sharing flow within the assessment timebox.”

Show the account selector. Explain that the three identities are demo users.

## 0:25–1:20 — Create, format, and save

Create a document, rename it, and add text. Show bold, italic, underline, a
heading, and a list. Point to autosave. Refresh and reopen the saved document
to demonstrate persistence and formatting.

## 1:20–2:10 — Sharing

As Ahmed, grant Sara access. Switch to Sara, show the Shared badge, and edit.
Switch back to Ahmed to reopen the update. Show that Omar has no access.
Explain that the owner manages sharing and can remove access.

## 2:10–2:40 — Import

Import `samples/team-notes.txt`, show its title and editable content, and explain
the `.txt`, encoding, and size constraints visible in the interface.

## 2:40–3:20 — Engineering choices

Explain the browser modules, feature routes/services, and SQLite flow, Delta JSON formatting, permission
checks, and the need for a persistent deployment volume. Demonstrate a two-tab
save conflict if time allows; explain that concurrent edits are not live-merged.

## 3:20–4:00 — Tradeoffs, tests, and AI

Show the backend and frontend tests. Briefly show the separated routes, services, and UI modules. Explain how AI helped implement and test the
code, what you reviewed or changed yourself, and any remaining limitations.
Be specific about what you actually checked; do not read unverified claims.
Mention real auth, live collaboration, and DOCX support as deliberate scope cuts.

Upload the recording to Loom, YouTube, Vimeo, or Google Drive with reviewer
access enabled. Put its real URL in `VIDEO_URL.txt` and `SUBMISSION.md`.

======================================================================
FILE: app/__init__.py
======================================================================


======================================================================
FILE: app/routes/__init__.py
======================================================================


======================================================================
FILE: app/routes/documents.py
======================================================================
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

======================================================================
FILE: app/routes/health.py
======================================================================
from fastapi import APIRouter, Depends
from app.dependencies import get_database

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(db=Depends(get_database, scope="function")):
    db.execute("SELECT 1 FROM users LIMIT 1")
    return {"status": "ok"}

======================================================================
FILE: app/routes/sharing.py
======================================================================
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

======================================================================
FILE: app/routes/users.py
======================================================================
from fastapi import APIRouter, Depends
from app.dependencies import get_database
from app.schemas import UserResponse

router = APIRouter(tags=["Demo users"])


@router.get("/users", response_model=list[UserResponse])
def list_users(db=Depends(get_database, scope="function")):
    return [dict(row) for row in db.execute("SELECT * FROM users ORDER BY id")]

======================================================================
FILE: app/services/__init__.py
======================================================================


======================================================================
FILE: app/services/documents.py
======================================================================
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

======================================================================
FILE: app/services/imports.py
======================================================================
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

======================================================================
FILE: app/services/sharing.py
======================================================================
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

======================================================================
FILE: compose.yaml
======================================================================
services:
  folio:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_PATH: /data/folio.db
    volumes:
      - folio-data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

volumes:
  folio-data:

======================================================================
FILE: download_vendor.py
======================================================================
import hashlib
import urllib.request
from pathlib import Path

directory = Path(__file__).resolve().parent / "static" / "vendor"
directory.mkdir(parents=True, exist_ok=True)
assets = {
    "quill.js": ("dist/quill.js", "f6157c72ac9b3f51cdead426335688a027b12405d9d6a4daadd38a676b2d7ff2"),
    "quill.snow.css": ("dist/quill.snow.css", "1c7948cd13aa92fac6390319bc1e5e461823da171519d3a768db56164f871636"),
    "QUILL-LICENSE.txt": ("LICENSE", "395c12b616d6f58238b4be39284d4d9221b58dd6e1f1e34d9ab537e34abbb022"),
}
for filename, (source, expected_hash) in assets.items():
    with urllib.request.urlopen("https://cdn.jsdelivr.net/npm/quill@2.0.3/" + source, timeout=30) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise RuntimeError("Unexpected asset checksum: " + filename)
    (directory / filename).write_bytes(content)
    print("Ready:", filename)

======================================================================
FILE: package-lock.json
======================================================================
{
  "name": "folio-document-editor",
  "version": "1.1.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "folio-document-editor",
      "version": "1.1.0",
      "devDependencies": {
        "linkedom": "0.18.12"
      }
    },
    "node_modules/boolbase": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/boolbase/-/boolbase-1.0.0.tgz",
      "integrity": "sha512-JZOSA7Mo9sNGB8+UjSgzdLtokWAky1zbztM3WRLCbZ70/3cTANmQmOdR7y2g+J0e2WXywy1yS468tY+IruqEww==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/css-select": {
      "version": "5.2.2",
      "resolved": "https://registry.npmjs.org/css-select/-/css-select-5.2.2.tgz",
      "integrity": "sha512-TizTzUddG/xYLA3NXodFM0fSbNizXjOKhqiQQwvhlspadZokn1KDy0NZFS0wuEubIYAV5/c1/lAr0TaaFXEXzw==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "boolbase": "^1.0.0",
        "css-what": "^6.1.0",
        "domhandler": "^5.0.2",
        "domutils": "^3.0.1",
        "nth-check": "^2.0.1"
      },
      "funding": {
        "url": "https://github.com/sponsors/fb55"
      }
    },
    "node_modules/css-what": {
      "version": "6.2.2",
      "resolved": "https://registry.npmjs.org/css-what/-/css-what-6.2.2.tgz",
      "integrity": "sha512-u/O3vwbptzhMs3L1fQE82ZSLHQQfto5gyZzwteVIEyeaY5Fc7R4dapF/BvRoSYFeqfBk4m0V1Vafq5Pjv25wvA==",
      "dev": true,
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">= 6"
      },
      "funding": {
        "url": "https://github.com/sponsors/fb55"
      }
    },
    "node_modules/cssom": {
      "version": "0.5.0",
      "resolved": "https://registry.npmjs.org/cssom/-/cssom-0.5.0.tgz",
      "integrity": "sha512-iKuQcq+NdHqlAcwUY0o/HL69XQrUaQdMjmStJ8JFmUaiiQErlhrmuigkg/CU4E2J0IyUKUrMAgl36TvN67MqTw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/dom-serializer": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/dom-serializer/-/dom-serializer-2.0.0.tgz",
      "integrity": "sha512-wIkAryiqt/nV5EQKqQpo3SToSOV9J0DnbJqwK7Wv/Trc92zIAYZ4FlMu+JPFW1DfGFt81ZTCGgDEabffXeLyJg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "domelementtype": "^2.3.0",
        "domhandler": "^5.0.2",
        "entities": "^4.2.0"
      },
      "funding": {
        "url": "https://github.com/cheeriojs/dom-serializer?sponsor=1"
      }
    },
    "node_modules/domelementtype": {
      "version": "2.3.0",
      "resolved": "https://registry.npmjs.org/domelementtype/-/domelementtype-2.3.0.tgz",
      "integrity": "sha512-OLETBj6w0OsagBwdXnPdN0cnMfF9opN69co+7ZrbfPGrdpPVNBUj02spi6B1N7wChLQiPn4CSH/zJvXw56gmHw==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/fb55"
        }
      ],
      "license": "BSD-2-Clause"
    },
    "node_modules/domhandler": {
      "version": "5.0.3",
      "resolved": "https://registry.npmjs.org/domhandler/-/domhandler-5.0.3.tgz",
      "integrity": "sha512-cgwlv/1iFQiFnU96XXgROh8xTeetsnJiDsTc7TYCLFd9+/WNkIqPTxiM/8pSd8VIrhXGTf1Ny1q1hquVqDJB5w==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "domelementtype": "^2.3.0"
      },
      "engines": {
        "node": ">= 4"
      },
      "funding": {
        "url": "https://github.com/fb55/domhandler?sponsor=1"
      }
    },
    "node_modules/domutils": {
      "version": "3.2.2",
      "resolved": "https://registry.npmjs.org/domutils/-/domutils-3.2.2.tgz",
      "integrity": "sha512-6kZKyUajlDuqlHKVX1w7gyslj9MPIXzIFiz/rGu35uC1wMi+kMhQwGhl4lt9unC9Vb9INnY9Z3/ZA3+FhASLaw==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "dom-serializer": "^2.0.0",
        "domelementtype": "^2.3.0",
        "domhandler": "^5.0.3"
      },
      "funding": {
        "url": "https://github.com/fb55/domutils?sponsor=1"
      }
    },
    "node_modules/entities": {
      "version": "4.5.0",
      "resolved": "https://registry.npmjs.org/entities/-/entities-4.5.0.tgz",
      "integrity": "sha512-V0hjH4dGPh9Ao5p0MoRY6BVqtwCjhz6vI5LT8AJ55H+4g9/4vbHx1I54fS0XuclLhDHArPQCiMjDxjaL8fPxhw==",
      "dev": true,
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">=0.12"
      },
      "funding": {
        "url": "https://github.com/fb55/entities?sponsor=1"
      }
    },
    "node_modules/html-escaper": {
      "version": "3.0.3",
      "resolved": "https://registry.npmjs.org/html-escaper/-/html-escaper-3.0.3.tgz",
      "integrity": "sha512-RuMffC89BOWQoY0WKGpIhn5gX3iI54O6nRA0yC124NYVtzjmFWBIiFd8M0x+ZdX0P9R4lADg1mgP8C7PxGOWuQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/htmlparser2": {
      "version": "10.1.0",
      "resolved": "https://registry.npmjs.org/htmlparser2/-/htmlparser2-10.1.0.tgz",
      "integrity": "sha512-VTZkM9GWRAtEpveh7MSF6SjjrpNVNNVJfFup7xTY3UpFtm67foy9HDVXneLtFVt4pMz5kZtgNcvCniNFb1hlEQ==",
      "dev": true,
      "funding": [
        "https://github.com/fb55/htmlparser2?sponsor=1",
        {
          "type": "github",
          "url": "https://github.com/sponsors/fb55"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "domelementtype": "^2.3.0",
        "domhandler": "^5.0.3",
        "domutils": "^3.2.2",
        "entities": "^7.0.1"
      }
    },
    "node_modules/htmlparser2/node_modules/entities": {
      "version": "7.0.1",
      "resolved": "https://registry.npmjs.org/entities/-/entities-7.0.1.tgz",
      "integrity": "sha512-TWrgLOFUQTH994YUyl1yT4uyavY5nNB5muff+RtWaqNVCAK408b5ZnnbNAUEWLTCpum9w6arT70i1XdQ4UeOPA==",
      "dev": true,
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">=0.12"
      },
      "funding": {
        "url": "https://github.com/fb55/entities?sponsor=1"
      }
    },
    "node_modules/linkedom": {
      "version": "0.18.12",
      "resolved": "https://registry.npmjs.org/linkedom/-/linkedom-0.18.12.tgz",
      "integrity": "sha512-jalJsOwIKuQJSeTvsgzPe9iJzyfVaEJiEXl+25EkKevsULHvMJzpNqwvj1jOESWdmgKDiXObyjOYwlUqG7wo1Q==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "css-select": "^5.1.0",
        "cssom": "^0.5.0",
        "html-escaper": "^3.0.3",
        "htmlparser2": "^10.0.0",
        "uhyphen": "^0.2.0"
      },
      "engines": {
        "node": ">=16"
      },
      "peerDependencies": {
        "canvas": ">= 2"
      },
      "peerDependenciesMeta": {
        "canvas": {
          "optional": true
        }
      }
    },
    "node_modules/nth-check": {
      "version": "2.1.1",
      "resolved": "https://registry.npmjs.org/nth-check/-/nth-check-2.1.1.tgz",
      "integrity": "sha512-lqjrjmaOoAnWfMmBPL+XNnynZh2+swxiX3WUE0s4yEHI6m+AwrK2UZOimIRl3X/4QctVqS8AiZjFqyOGrMXb/w==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "boolbase": "^1.0.0"
      },
      "funding": {
        "url": "https://github.com/fb55/nth-check?sponsor=1"
      }
    },
    "node_modules/uhyphen": {
      "version": "0.2.0",
      "resolved": "https://registry.npmjs.org/uhyphen/-/uhyphen-0.2.0.tgz",
      "integrity": "sha512-qz3o9CHXmJJPGBdqzab7qAYuW8kQGKNEuoHFYrBwV6hWIMcpAmxDLXojcHfFr9US1Pe6zUswEIJIbLI610fuqA==",
      "dev": true,
      "license": "ISC"
    }
  }
}

======================================================================
FILE: package.json
======================================================================
{
  "name": "folio-document-editor",
  "private": true,
  "version": "1.1.0",
  "type": "module",
  "scripts": {
    "test": "node --test tests/frontend/*.test.js"
  },
  "devDependencies": {
    "linkedom": "0.18.12"
  }
}

======================================================================
FILE: railway.json
======================================================================
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "DOCKERFILE" },
  "deploy": { "healthcheckPath": "/api/health", "restartPolicyType": "ON_FAILURE" }
}

======================================================================
FILE: requirements.txt
======================================================================
fastapi==0.141.1
uvicorn==0.52.1
python-multipart==0.0.32
httpx==0.28.1

======================================================================
FILE: samples/team-notes.txt
======================================================================
Team planning notes

Goal: Make shared work easier to find and update.

This week:
1. Review the first product slice.
2. Share this document with Sara.
3. Agree on the next milestone.

======================================================================
FILE: static/index.html
======================================================================
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Folio — A little room for your best work</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="/static/vendor/quill.snow.css">
  <link rel="stylesheet" href="/static/styles.css">
  <script defer src="/static/vendor/quill.js"></script>
  <script type="module" src="/static/js/app.js"></script>
</head>
<body>
  <aside class="sidebar">
    <a class="brand" href="/" aria-label="Folio home"><span class="brand-icon">f</span> folio<span class="brand-dot">.</span></a>
    <p class="workspace-label">YOUR WORKSPACE</p>
    <button id="new-document" class="primary wide">+ &nbsp; New document</button>
    <button id="import-document" class="secondary wide">↑ &nbsp; Import text file</button>
    <p class="import-hint">UTF-8 .txt · 1 MB · 100k characters</p>
    <input id="file-input" type="file" accept=".txt,text/plain" hidden>
    <label class="search"><span>⌕</span><input id="search" placeholder="Find a document…" aria-label="Find a document"></label>
    <nav class="filters" aria-label="Filter documents">
      <button data-filter="all" class="active">All files</button>
      <button data-filter="owned">Owned</button>
      <button data-filter="shared">Shared</button>
    </nav>
    <div class="list-heading"><span>DOCUMENTS</span><span id="document-count">0</span><button id="refresh-documents" aria-label="Refresh document list" title="Refresh document list">↻</button></div>
    <div id="document-list" aria-label="Documents"></div>
    <footer class="account">
      <div class="avatar" id="avatar">AA</div>
      <div class="account-info"><label for="user-select">Demo account</label><select id="user-select" aria-label="Demo account"></select></div>
      <p>Switch accounts to try sharing. Demo identities are simulated.</p>
    </footer>
  </aside>
  <main>
    <header class="topbar"><span>Workspace <span class="slash">/</span> <strong id="breadcrumb">Your documents</strong></span><span class="workspace-badge">A SPACE TO THINK</span></header>
    <section id="empty-state" class="empty-state">
      <div class="empty-icon">✦</div><p class="eyebrow">GOOD IDEAS START HERE</p>
      <h1>A little room for<br>your best work.</h1>
      <p>Create a document, bring your notes,<br>and move things forward together.</p>
      <button id="empty-create" class="primary">Create your first document &nbsp; →</button>
      <div class="empty-features"><span>Rich text</span><span>Autosave</span><span>Simple sharing</span></div>
    </section>
    <section id="document-panel" hidden>
      <div class="document-header">
        <div class="title-area"><div class="eyebrow">DOCUMENT <span id="ownership" class="badge">Owned by you</span></div><input id="document-title" maxlength="120" aria-label="Document title" placeholder="Untitled document"></div>
        <div class="document-actions"><button id="download-draft" class="secondary" title="Download a plain-text copy of the current draft">Download draft</button><button id="reload-document" class="secondary">Reload latest</button><button id="save-document" class="secondary">Save</button><button id="share-document" class="primary">Share ↗</button></div>
      </div>
      <div class="document-meta"><span id="owner-label"></span><span id="save-status" role="status">Saved</span></div>
      <div id="conflict-banner" class="conflict" hidden>Your draft is kept here. Another user saved a newer version. Use “Download draft” to keep a text copy before choosing “Reload latest”.</div>
      <div class="editor-workspace">
        <div id="toolbar" aria-label="Text formatting">
          <span class="ql-formats"><select class="ql-header" aria-label="Text style"><option selected value="">Normal text</option><option value="1">Heading 1</option><option value="2">Heading 2</option><option value="3">Heading 3</option></select></span>
          <span class="ql-formats"><button class="ql-bold" aria-label="Bold"></button><button class="ql-italic" aria-label="Italic"></button><button class="ql-underline" aria-label="Underline"></button></span>
          <span class="ql-formats"><button class="ql-list" value="bullet" aria-label="Bulleted list"></button><button class="ql-list" value="ordered" aria-label="Numbered list"></button></span>
          <span class="toolbar-note">MAKE SOMETHING GOOD</span>
        </div>
        <div class="paper"><div id="editor"></div></div>
        <div class="editor-footer"><span id="word-count">0 words</span><span>Changes save automatically</span></div>
      </div>
    </section>
    <div id="notice" role="alert" hidden></div>
  </main>
  <dialog id="share-dialog" aria-labelledby="share-heading">
    <div class="dialog-heading"><h2 id="share-heading">Better, together.</h2><button id="close-share" class="icon-button" aria-label="Close sharing">×</button></div>
    <p>Invite a teammate to edit this document.<br>Only the owner can manage access.</p>
    <div class="invite"><select id="share-user" aria-label="Teammate to invite"></select><button id="grant-access" class="primary">Give access</button></div>
    <h3>People with access</h3><div id="share-list"></div>
    <p class="dialog-note">Shared editing is asynchronous. Conflicting saves are detected; live cursors and merging are out of scope.</p>
  </dialog>
</body>
</html>

======================================================================
FILE: static/js/api.js
======================================================================
import { state } from "./state.js";

export async function api(path, options = {}) {
  const { userId = state.userId, ...request } = options;
  const headers = new Headers(request.headers);
  headers.set("X-User-Id", String(userId));
  if (request.body && !(request.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/api${path}`, { ...request, headers, signal: controller.signal });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      let message = body.detail || "Something went wrong. Please try again.";
      if (Array.isArray(message)) message = message.map((item) => item.msg).join(" ");
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out. Your unsaved draft is still here.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and retry.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

======================================================================
FILE: static/js/app.js
======================================================================
import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state, storedUserId } from "./state.js";
import { createEditor, downloadDraft, updateWordCount } from "./editor.js";
import { createSaveManager } from "./autosave.js";
import { createDocumentController } from "./documents.js";
import { initializeSharing } from "./sharing.js";
import { renderDocuments, setBusy, updateAccount, setSaveStatus } from "./view.js";

let saves;
const editor = createEditor(markChanged);
saves = createSaveManager({
  readSnapshot: () => ({
    id: state.current.id,
    title: $("document-title").value,
    content: editor.getContents(),
    version: state.current.version
  }),
  writeSnapshot: ({ id, ...payload }) => api(`/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  onSaved: (saved) => {
    state.current.version = saved.version;
    state.current.title = saved.title;
    state.current.updated_at = saved.updated_at;
    state.documents = state.documents.map((document) => document.id === saved.id ? saved : document);
    $("breadcrumb").textContent = saved.title;
    renderDocuments();
  },
  onStatus: setSaveStatus,
  onError: (error) => notify(error.message, true)
});
const documents = createDocumentController(editor, saves);
initializeSharing(documents);

function markChanged() {
  if (!state.current || state.busy) return;
  saves.changed();
  updateWordCount(editor);
}

$("new-document").addEventListener("click", documents.create);
$("empty-create").addEventListener("click", documents.create);
$("document-title").addEventListener("input", markChanged);
$("save-document").addEventListener("click", () => { if (!state.busy) saves.flush(); });
$("reload-document").addEventListener("click", documents.reload);
$("download-draft").addEventListener("click", () => downloadDraft(editor));
$("refresh-documents").addEventListener("click", documents.refresh);
$("search").addEventListener("input", renderDocuments);
$("document-list").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-document-id]");
  if (button) documents.open(Number(button.dataset.documentId));
});
for (const button of document.querySelectorAll("[data-filter]")) button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
  renderDocuments();
});
$("user-select").addEventListener("change", (event) => documents.switchUser(Number(event.target.value)));
$("import-document").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  documents.importFile(file);
});
window.addEventListener("beforeunload", (event) => {
  if (saves.dirty || saves.saving) { event.preventDefault(); event.returnValue = ""; }
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    if (!state.busy) saves.flush();
  }
});

async function initialize() {
  setBusy(editor, true);
  try {
    state.users = await api("/users");
    const stored = storedUserId();
    state.userId = state.users.some((user) => user.id === stored) ? stored : 1;
    $("user-select").replaceChildren(...state.users.map((user) => new Option(user.name, user.id)));
    updateAccount();
    await documents.load();
  } catch (error) {
    notify(`Could not load your workspace: ${error.message}`, true);
  } finally {
    setBusy(editor, false);
  }
}
initialize();

======================================================================
FILE: static/js/autosave.js
======================================================================
export function createSaveManager({ readSnapshot, writeSnapshot, onSaved, onStatus, onError, delay = 900 }) {
  let revision = 0;
  let savedRevision = 0;
  let pending = null;
  let timer = null;
  let conflict = false;

  function isDirty() {
    return revision !== savedRevision;
  }

  function schedule() {
    clearTimeout(timer);
    if (!conflict) timer = setTimeout(save, delay);
  }

  function changed() {
    revision += 1;
    onStatus(conflict ? "conflict" : "unsaved");
    schedule();
  }

  async function save() {
    clearTimeout(timer);
    if (pending) return pending;
    if (!isDirty()) return true;
    if (conflict) return false;
    const snapshot = readSnapshot();
    if (!snapshot.title.trim()) {
      onStatus("invalid");
      onError(new Error("Give your document a title before saving."));
      return false;
    }
    snapshot.title = snapshot.title.trim();
    const savingRevision = revision;
    onStatus("saving");
    pending = (async () => {
      try {
        const saved = await writeSnapshot(snapshot);
        onSaved(saved, snapshot);
        savedRevision = savingRevision;
        onStatus(isDirty() ? "unsaved" : "saved");
        if (isDirty()) schedule();
        return true;
      } catch (error) {
        conflict = error.status === 409;
        onStatus(conflict ? "conflict" : "error");
        onError(error);
        return false;
      } finally {
        pending = null;
      }
    })();
    return pending;
  }

  async function flush() {
    if (pending && !await pending) return false;
    while (isDirty()) {
      if (!await save()) return false;
    }
    return true;
  }

  function reset() {
    if (pending) throw new Error("Wait for the current save before changing documents.");
    clearTimeout(timer);
    revision = 0;
    savedRevision = 0;
    conflict = false;
    onStatus("saved");
  }

  return {
    changed, save, flush, reset,
    waitForPending: () => pending || Promise.resolve(true),
    get dirty() { return isDirty(); },
    get saving() { return Boolean(pending); },
    get conflict() { return conflict; }
  };
}

======================================================================
FILE: static/js/documents.js
======================================================================
import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state, rememberUserId } from "./state.js";
import { renderDocuments, showDocument, setBusy, resetFilters, updateAccount } from "./view.js";

export function createDocumentController(editor, saves) {
  function setDocument(document) {
    saves.reset();
    state.current = document;
    showDocument(editor);
  }

  async function navigate(action, save = true) {
    if (state.busy) return false;
    setBusy(editor, true);
    try {
      if (save && !await saves.flush()) return false;
      await action();
      return true;
    } catch (error) {
      notify(error.message, true);
      return false;
    } finally {
      setBusy(editor, false);
    }
  }

  async function load() {
    state.documents = await api("/documents");
    renderDocuments();
  }

  function open(id) {
    if (state.current?.id === id) return;
    return navigate(async () => setDocument(await api(`/documents/${id}`)));
  }

  async function create() {
    const created = await navigate(async () => {
      const document = await api("/documents", {
        method: "POST", body: JSON.stringify({ title: "Untitled document" })
      });
      state.documents.unshift(document);
      resetFilters();
      setDocument(document);
    });
    if (created) {
      $("document-title").focus();
      $("document-title").select();
    }
  }

  async function importFile(file) {
    if (!file) return;
    if (!/\.txt$/i.test(file.name) || file.size > 1024 * 1024) {
      notify("Choose a UTF-8 .txt file under 1 MB.", true);
      return;
    }
    await navigate(async () => {
      const data = new FormData();
      data.append("file", file);
      const document = await api("/documents/import", { method: "POST", body: data });
      state.documents.unshift(document);
      resetFilters();
      setDocument(document);
      notify("Your notes are ready to edit.");
    });
  }

  async function switchUser(userId) {
    await navigate(async () => {
      const documents = await api("/documents", { userId });
      state.userId = userId;
      state.documents = documents;
      rememberUserId(userId);
      resetFilters();
      updateAccount();
      setDocument(null);
    });
    $("user-select").value = state.userId;
  }

  function reload() {
    return navigate(async () => {
      await saves.waitForPending();
      if (saves.dirty && !confirm("Discard your unsaved draft? Download a text copy first if you need to keep it.")) return;
      setDocument(await api(`/documents/${state.current.id}`));
    }, false);
  }

  return { open, create, importFile, switchUser, reload, load, navigate, refresh: () => navigate(load) };
}

======================================================================
FILE: static/js/dom.js
======================================================================
let noticeTimer;

export function $(id) {
  return document.getElementById(id);
}

export function notify(message, error = false) {
  clearTimeout(noticeTimer);
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
  $("notice").hidden = false;
  noticeTimer = setTimeout(() => { $("notice").hidden = true; }, error ? 10000 : 4000);
}

======================================================================
FILE: static/js/editor.js
======================================================================
import { $ } from "./dom.js";

export function createEditor(onChange) {
  const editor = new Quill("#editor", {
    theme: "snow",
    placeholder: "Start with a thought…",
    formats: ["bold", "italic", "underline", "header", "list"],
    modules: { toolbar: "#toolbar" }
  });
  editor.root.setAttribute("aria-label", "Document content");
  editor.root.setAttribute("role", "textbox");
  editor.root.setAttribute("aria-multiline", "true");
  editor.on("text-change", (delta, previous, source) => {
    if (source === "user") onChange();
  });
  return editor;
}

export function updateWordCount(editor) {
  const text = editor.getText().trim();
  const words = text ? text.split(/\s+/).length : 0;
  $("word-count").textContent = `${words} ${words === 1 ? "word" : "words"}`;
}

export function downloadDraft(editor) {
  const title = $("document-title").value.trim() || "Untitled document";
  const content = `${title}\n\n${editor.getText()}`;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 90) + ".txt";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

======================================================================
FILE: static/js/sharing.js
======================================================================
import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state } from "./state.js";

export function initializeSharing(documents) {
  let busy = false;

  function setBusy(value) {
    busy = value;
    for (const button of $("share-dialog").querySelectorAll("button")) button.disabled = value;
    $("share-user").disabled = value;
    $("grant-access").disabled = value || !$("share-user").value;
  }

  async function render() {
    const shares = await api(`/documents/${state.current.id}/shares`);
    const owner = state.users.find((user) => user.id === state.current.owner_id);
    const list = $("share-list");
    list.replaceChildren();
    for (const user of [owner, ...shares]) {
      const row = document.createElement("div");
      row.className = "member";
      const name = document.createElement("span");
      name.textContent = user.name;
      const email = document.createElement("small");
      email.textContent = user.email;
      name.append(email);
      const role = document.createElement(user.id === owner.id ? "span" : "button");
      role.className = "member-role";
      role.textContent = user.id === owner.id ? "Owner" : "Remove access";
      if (user.id !== owner.id) role.dataset.userId = user.id;
      row.append(name, role);
      list.append(row);
    }
    const available = state.users.filter((user) => user.id !== owner.id && !shares.some((share) => share.id === user.id));
    $("share-user").replaceChildren(...available.map((user) => new Option(user.name, user.id)));
    if (!available.length) $("share-user").append(new Option("Everyone already has access", ""));
    setBusy(false);
  }

  async function changeAccess(action) {
    if (busy) return;
    setBusy(true);
    try {
      await action();
      await render();
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  $("share-document").addEventListener("click", () => documents.navigate(async () => {
    await render();
    $("share-dialog").showModal();
  }));
  $("close-share").addEventListener("click", () => $("share-dialog").close());
  $("share-dialog").addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
  $("grant-access").addEventListener("click", () => {
    const userId = Number($("share-user").value);
    changeAccess(async () => {
      await api(`/documents/${state.current.id}/shares`, {
        method: "POST", body: JSON.stringify({ user_id: userId })
      });
      notify("Editor access granted. Switch demo accounts to try it.");
    });
  });
  $("share-list").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-user-id]");
    if (!button) return;
    changeAccess(() => api(`/documents/${state.current.id}/shares/${button.dataset.userId}`, { method: "DELETE" }));
  });
}

======================================================================
FILE: static/js/state.js
======================================================================
export const state = {
  users: [],
  documents: [],
  current: null,
  userId: 1,
  filter: "all",
  busy: false
};

export function storedUserId() {
  try { return Number(sessionStorage.getItem("folio-user")) || 1; }
  catch { return 1; }
}

export function rememberUserId(userId) {
  try { sessionStorage.setItem("folio-user", String(userId)); }
  catch { /* Account persistence is optional; document saves still use the API. */ }
}

======================================================================
FILE: static/js/view.js
======================================================================
import { $ } from "./dom.js";
import { state } from "./state.js";
import { updateWordCount } from "./editor.js";

export function renderDocuments() {
  const list = $("document-list");
  list.replaceChildren();
  const search = $("search").value.toLowerCase();
  const documents = state.documents.filter((document) => {
    const owned = document.owner_id === state.userId;
    return document.title.toLowerCase().includes(search) &&
      (state.filter === "all" || (state.filter === "owned" && owned) || (state.filter === "shared" && !owned));
  });
  $("document-count").textContent = documents.length;
  for (const item of documents) {
    const button = document.createElement("button");
    button.className = "document-item" + (item.id === state.current?.id ? " selected" : "");
    button.disabled = state.busy;
    if (item.id === state.current?.id) button.setAttribute("aria-current", "page");
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = "▤";
    const info = document.createElement("span");
    info.className = "file-info";
    const title = document.createElement("span");
    title.className = "file-title";
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "file-meta";
    const owner = item.owner_id === state.userId ? "Owned by you" : `Shared by ${item.owner_name.split(" ")[0]}`;
    meta.textContent = `${owner} · ${new Date(item.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
    info.append(title, meta);
    button.append(icon, info);
    button.dataset.documentId = item.id;
    list.append(button);
  }
  if (!documents.length) {
    const empty = document.createElement("p");
    empty.className = "list-empty";
    empty.textContent = state.documents.length ? "No matching documents." : "Your next idea belongs here. Create a document or import your notes.";
    list.append(empty);
  }
}

export function showDocument(editor) {
  const document = state.current;
  $("empty-state").hidden = Boolean(document);
  $("document-panel").hidden = !document;
  $("breadcrumb").textContent = document?.title || "Your documents";
  if (document) {
    const owned = document.owner_id === state.userId;
    $("document-title").value = document.title;
    editor.setContents(document.content, "silent");
    $("ownership").textContent = owned ? "Owned by you" : "Shared with you";
    $("owner-label").textContent = `${document.owner_name} · ${owned ? "Owner" : "You have editor access"}`;
    $("share-document").hidden = !owned;
    updateWordCount(editor);
  }
  renderDocuments();
}

export function setBusy(editor, value) {
  state.busy = value;
  for (const id of ["new-document", "empty-create", "import-document", "user-select", "save-document",
    "reload-document", "share-document", "document-title", "refresh-documents"]) {
    $(id).disabled = value;
  }
  editor.enable(!value && Boolean(state.current));
  renderDocuments();
}

export function resetFilters() {
  state.filter = "all";
  $("search").value = "";
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.classList.toggle("active", button.dataset.filter === "all");
  }
}

export function updateAccount() {
  const user = state.users.find((user) => user.id === state.userId);
  $("user-select").value = state.userId;
  $("avatar").textContent = user.name.split(" ").map((word) => word[0]).join("");
}

export function setSaveStatus(status) {
  const messages = {
    saved: "All changes saved",
    unsaved: "Unsaved changes",
    saving: "Saving…",
    error: "Save failed · try again",
    invalid: "A title is required",
    conflict: "Conflict · draft kept"
  };
  $("save-status").textContent = messages[status];
  $("conflict-banner").hidden = status !== "conflict";
}

======================================================================
FILE: static/styles.css
======================================================================
* {
  box-sizing:border-box;
}
:root {
  --ink:#192d2b;
  --muted:#75827c;
  --accent:#285c4d;
  --line:#e3e8e1;
  --paper:#fff;
  --cream:#f4f5ef;
}
body {
  margin:0;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
  color:var(--ink);
  background:var(--cream);
}
button,input,select {
  font:inherit;
}
button,select {
  cursor:pointer;
}
button {
  border:0;
  transition:background .15s,transform .15s;
}
button:disabled,select:disabled {
  opacity:.5;
  cursor:wait;
}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible {
  outline:3px solid #bdcf82;
  outline-offset:3px;
}
button:hover:not(:disabled) {
  filter:brightness(.95);
}
[hidden] {
  display:none!important;
}
.sidebar {
  position:fixed;
  inset:0 auto 0 0;
  width:280px;
  padding:36px 23px 18px;
  background:#fff;
  border-right:1px solid var(--line);
  display:flex;
  flex-direction:column;
  z-index:2;
}
.brand {
  display:flex;
  align-items:center;
  text-decoration:none;
  color:var(--ink);
  font-size:35px;
  font-weight:750;
  letter-spacing:-2px;
  margin:0 0 40px 5px;
}
.brand-icon {
  display:inline-grid;
  place-items:center;
  width:37px;
  height:43px;
  background:var(--accent);
  border-radius:8px 8px 17px 8px;
  color:#fff;
  font:italic 36px Georgia;
  margin-right:12px;
  letter-spacing:0;
}
.brand-dot {
  color:#b4c978;
}
.workspace-label,.list-heading,.eyebrow {
  font-size:10px;
  letter-spacing:1.7px;
  font-weight:700;
  color:var(--muted);
}
.workspace-label {
  margin:0 0 15px 4px;
}
.primary,.secondary {
  padding:11px 17px;
  border-radius:7px;
  font-size:13px;
  font-weight:600;
  white-space:nowrap;
}
.primary {
  background:var(--accent);
  color:#fff;
  box-shadow:0 2px 3px #16382a14;
}
.secondary {
  background:#fff;
  border:1px solid var(--line);
  color:#39544a;
}
.wide {
  width:100%;
  text-align:left;
  margin-bottom:9px;
}
.import-hint {
  font-size:10px;
  color:#86918b;
  margin:3px 0 27px;
  text-align:center;
}
.search {
  display:flex;
  align-items:center;
  gap:9px;
  padding:10px;
  border:1px solid var(--line);
  border-radius:7px;
  color:#8b978f;
}
.search input {
  min-width:0;
  width:100%;
  border:0;
  outline:0;
  font-size:12px;
  background:none;
}
.filters {
  display:flex;
  gap:4px;
  margin:18px 0 24px;
}
.filters button {
  padding:7px 10px;
  border-radius:5px;
  background:none;
  color:var(--muted);
  font-size:11px;
}
.filters .active {
  color:var(--accent);
  background:#eaf0e6;
  font-weight:650;
}
.list-heading {
  display:flex;
  justify-content:space-between;
  padding:0 4px 13px;
  font-size:9px;
}
.list-heading span:last-child {
  letter-spacing:0;
}
#refresh-documents {
  background:none;
  color:var(--accent);
  font-size:16px;
  padding:0 2px;
}
#document-count {
  margin-left:auto;
  margin-right:12px;
  align-self:center;
}
#document-list {
  overflow-y:auto;
  flex:1;
  min-height:70px;
}
.document-item {
  display:flex;
  gap:11px;
  width:100%;
  text-align:left;
  border-radius:7px;
  padding:13px 10px;
  margin-bottom:5px;
  background:none;
  color:var(--ink);
}
.document-item.selected {
  background:#edf2e8;
}
.file-icon {
  font-size:21px;
  color:#95a388;
}
.file-info {
  overflow:hidden;
  display:flex;
  flex-direction:column;
  gap:5px;
}
.file-title {
  font-weight:600;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:12px;
}
.file-meta {
  font-size:10px;
  color:var(--muted);
}
.list-empty {
  font-size:12px;
  line-height:1.7;
  color:var(--muted);
  padding:10px;
}
.account {
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  border-top:1px solid var(--line);
  padding-top:18px;
  margin-top:20px;
}
.avatar {
  background:#ecdfcb;
  color:#745331;
  width:33px;
  height:33px;
  border-radius:50%;
  display:grid;
  place-items:center;
  font-size:11px;
  font-weight:650;
}
.account-info {
  flex:1;
}
.account-info label {
  font-size:9px;
  color:var(--muted);
  display:block;
  margin-bottom:4px;
}
.account-info select {
  border:0;
  width:100%;
  font-weight:600;
  font-size:12px;
  color:var(--ink);
  background:#fff;
}
.account p {
  font-size:10px;
  color:var(--muted);
  line-height:1.5;
  margin:2px 0;
}
main {
  margin-left:280px;
  min-height:100vh;
}
.topbar {
  height:80px;
  padding:0 40px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  border-bottom:1px solid var(--line);
  font-size:12px;
  color:var(--muted);
}
.topbar strong {
  font-weight:500;
  color:#476055;
}
.slash {
  margin:0 14px;
  color:#bdc5bc;
}
.workspace-badge {
  font-size:9px;
  letter-spacing:1.6px;
  border:1px solid #d6dece;
  padding:7px 10px;
  border-radius:4px;
  color:#76836c;
}
.empty-state {
  text-align:center;
  display:flex;
  flex-direction:column;
  align-items:center;
  padding:100px 24px;
}
.empty-icon {
  font-size:49px;
  color:#92a960;
  background:#e8eddb;
  width:98px;
  height:98px;
  border-radius:28px;
  display:grid;
  place-items:center;
  margin-bottom:23px;
  transform:rotate(-7deg);
}
.empty-state .eyebrow {
  color:#7b8d67;
}
.empty-state h1 {
  font:normal 54px/1.08 Georgia,serif;
  letter-spacing:-1.7px;
  margin:13px 0 18px;
}
.empty-state>p:not(.eyebrow) {
  font-size:14px;
  color:var(--muted);
  line-height:1.8;
  margin:0 0 26px;
}
.empty-features {
  display:flex;
  gap:22px;
  margin-top:35px;
  font-size:11px;
  color:#7d8b76;
}
.empty-features span::before {
  content:'✓';
  color:#8d9e62;
  margin-right:6px;
}
.document-header {
  padding:34px 40px 10px;
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:20px;
}
.title-area {
  min-width:0;
  flex:1;
}
.title-area .eyebrow {
  display:flex;
  gap:12px;
  align-items:center;
}
.badge {
  font-size:9px;
  letter-spacing:0;
  font-weight:500;
  background:#e7eddc;
  padding:4px 7px;
  border-radius:4px;
  color:#64774c;
}
#document-title {
  font:normal 30px Georgia,serif;
  background:none;
  border:0;
  color:var(--ink);
  width:100%;
  padding:9px 0 2px;
  outline-offset:0;
}
.document-actions {
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  justify-content:flex-end;
}
#reload-document {
  font-size:11px;
}
.document-meta {
  padding:0 40px 25px;
  display:flex;
  justify-content:space-between;
  font-size:11px;
  color:var(--muted);
}
#save-status::before {
  content:'●';
  font-size:8px;
  color:#799c55;
  margin-right:7px;
}
.editor-workspace {
  padding:0 40px 30px;
  max-width:1150px;
  margin:auto;
}
.ql-toolbar.ql-snow {
  border:1px solid var(--line);
  background:white;
  border-radius:8px;
  margin-bottom:26px;
  padding:10px 12px;
  display:flex;
  align-items:center;
  flex-wrap:wrap;
}
.ql-toolbar .ql-picker.ql-header {
  width:120px;
}
.ql-snow .ql-picker.ql-header .ql-picker-label::before {
  font-family:inherit;
  font-size:12px;
}
.toolbar-note {
  margin-left:auto;
  color:#a0aa98;
  font-size:8px;
  letter-spacing:1.4px;
  padding-right:8px;
}
.paper {
  max-width:815px;
  min-height:610px;
  margin:auto;
  background:white;
  border:1px solid #e5e8de;
  box-shadow:0 4px 20px #1c332805;
  border-radius:2px;
}
#editor {
  border:0;
  min-height:610px;
}
.ql-editor {
  padding:58px 66px;
  min-height:610px;
  font-size:15px;
  line-height:1.85;
  color:#34433b;
}
.ql-editor.ql-blank::before {
  left:66px;
  right:66px;
  top:58px;
  font-style:normal;
  color:#a4ada1;
}
.ql-editor h1,.ql-editor h2,.ql-editor h3 {
  font-family:Georgia,serif;
  font-weight:normal;
  color:var(--ink);
}
.ql-editor p {
  margin-bottom:9px;
}
.editor-footer {
  display:flex;
  justify-content:space-between;
  font-size:10px;
  color:#929e8a;
  max-width:815px;
  margin:15px auto 0;
}
.conflict {
  margin:0 40px 20px;
  background:#fff1d1;
  color:#8a5b13;
  padding:13px 17px;
  border-radius:7px;
  font-size:12px;
  line-height:1.6;
}
#notice {
  position:fixed;
  bottom:22px;
  left:calc(50% + 140px);
  transform:translateX(-50%);
  max-width:560px;
  width:max-content;
  padding:13px 20px;
  border-radius:8px;
  background:#233d32;
  color:white;
  box-shadow:0 6px 25px #0002;
  font-size:12px;
  z-index:6;
  line-height:1.6;
}
#notice.error {
  background:#8a3d34;
}
dialog {
  border:1px solid var(--line);
  border-radius:14px;
  padding:29px;
  width:min(490px,calc(100% - 30px));
  color:var(--ink);
  box-shadow:0 25px 100px #0002;
}
dialog::backdrop {
  background:#122d2444;
  backdrop-filter:blur(3px);
}
.dialog-heading {
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.dialog-heading h2 {
  font:normal 30px Georgia;
  margin:0;
}
.icon-button {
  background:none;
  font-size:25px;
  color:#6e7d70;
}
dialog p {
  font-size:12px;
  color:var(--muted);
  line-height:1.8;
}
.invite {
  display:flex;
  gap:9px;
  margin:24px 0;
}
.invite select {
  flex:1;
  min-width:0;
  padding:10px;
  border:1px solid var(--line);
  border-radius:6px;
  background:white;
  font-size:12px;
}
dialog h3 {
  font-size:11px;
  margin:25px 0 12px;
}
.member {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:12px 0;
  border-bottom:1px solid var(--line);
  font-size:12px;
}
.member small {
  color:var(--muted);
  display:block;
  margin-top:4px;
}
.member button {
  font-size:11px;
  background:none;
  color:#9a4a3d;
}
.member-role {
  color:var(--muted);
  font-size:11px;
}
.dialog-note {
  margin:23px 0 0;
  font-size:10px!important;
}
@media(min-width:1500px) {
  .editor-workspace {
    padding-top:10px;
  }
  .paper,#editor,.ql-editor {
    min-height:720px;
  }
}
@media(max-width:1050px) {
  .sidebar {
    width:240px;
    padding:28px 17px;
  }
  main {
    margin-left:240px;
  }
  .topbar {
    padding:0 25px;
  }
  .document-header {
    padding:25px 25px 10px;
    align-items:flex-start;
    flex-wrap:wrap;
  }
  .title-area {
    flex-basis:100%;
  }
  .document-meta {
    padding:0 25px 20px;
  }
  .editor-workspace {
    padding:0 25px 25px;
  }
  .toolbar-note {
    display:none;
  }
  #notice {
    left:calc(50% + 120px);
  }
  .ql-editor {
    padding:40px;
  }
  .ql-editor.ql-blank::before {
    left:40px;
    top:40px;
  }
}
@media(max-width:650px) {
  .sidebar {
    position:relative;
    width:100%;
    padding:20px;
    border-right:0;
    border-bottom:1px solid var(--line);
  }
  .brand {
    margin:0 0 22px;
    font-size:28px;
  }
  .brand-icon {
    width:30px;
    height:34px;
    font-size:28px;
  }
  .workspace-label,.import-hint,.account p {
    display:none;
  }
  .wide {
    width:auto;
    margin-right:5px;
  }
  .search {
    margin-top:12px;
  }
  .filters {
    margin:12px 0;
  }
  #document-list {
    max-height:160px;
    min-height:0;
  }
  .account {
    margin:14px 0 0;
    padding-top:13px;
  }
  .account-info select {
    max-width:200px;
  }
  .topbar {
    height:58px;
    padding:0 20px;
  }
  .workspace-badge {
    display:none;
  }
  main {
    margin-left:0;
  }
  .empty-state {
    padding:55px 20px;
  }
  .empty-state h1 {
    font-size:42px;
  }
  .document-header {
    padding:23px 20px 10px;
  }
  .document-meta {
    padding:0 20px 20px;
    gap:10px;
  }
  .editor-workspace {
    padding:0 12px 25px;
  }
  .ql-toolbar.ql-snow {
    margin-bottom:14px;
  }
  .ql-editor {
    padding:28px 24px;
    font-size:14px;
  }
  .ql-editor.ql-blank::before {
    left:24px;
    top:28px;
  }
  .paper,#editor,.ql-editor {
    min-height:450px;
  }
  #notice {
    left:50%;
    width:calc(100% - 30px);
  }
  .conflict {
    margin:0 20px 15px;
  }
}

======================================================================
FILE: tests/frontend/autosave.test.js
======================================================================
import test from "node:test";
import assert from "node:assert/strict";
import { createSaveManager } from "../../static/js/autosave.js";

function setup(write) {
  let draft = { id: 1, title: "Plan", content: { ops: [{ insert: "First draft\n" }] }, version: 1 };
  const statuses = [];
  const errors = [];
  const manager = createSaveManager({
    readSnapshot: () => structuredClone(draft),
    writeSnapshot: write,
    onSaved: (saved) => { draft.version = saved.version; },
    onStatus: (status) => statuses.push(status),
    onError: (error) => errors.push(error.message),
    delay: 60000
  });
  return { manager, statuses, errors, change: (title) => { draft.title = title; manager.changed(); } };
}

test("flush saves a valid changed document and clears unsaved state", async () => {
  const writes = [];
  const app = setup(async (snapshot) => { writes.push(snapshot); return { version: snapshot.version + 1 }; });
  app.change("Updated plan");
  assert.equal(await app.manager.flush(), true);
  assert.equal(writes[0].title, "Updated plan");
  assert.equal(app.manager.dirty, false);
  assert.equal(app.statuses.at(-1), "saved");
  app.manager.reset();
});

test("typing during an in-flight save is saved afterward with the new version", async () => {
  let finishFirst;
  const writes = [];
  const app = setup((snapshot) => {
    writes.push(snapshot);
    if (writes.length === 1) return new Promise((resolve) => { finishFirst = resolve; });
    return Promise.resolve({ version: snapshot.version + 1 });
  });
  app.change("First edit");
  const saving = app.manager.save();
  app.change("Second edit");
  finishFirst({ version: 2 });
  await saving;
  assert.equal(app.manager.dirty, true);
  assert.equal(await app.manager.flush(), true);
  assert.deepEqual(writes.map((snapshot) => [snapshot.title, snapshot.version]), [["First edit", 1], ["Second edit", 2]]);
  app.manager.reset();
});

test("overlapping save requests do not duplicate an in-flight write", async () => {
  let finish;
  let writes = 0;
  const app = setup(() => { writes += 1; return new Promise((resolve) => { finish = resolve; }); });
  app.change("An edit");
  const first = app.manager.save();
  const second = app.manager.save();
  assert.equal(writes, 1);
  finish({ version: 2 });
  await Promise.all([first, second]);
  assert.equal(app.manager.dirty, false);
  app.manager.reset();
});

test("a version conflict keeps the draft and stops automatic retries", async () => {
  let writes = 0;
  const app = setup(async () => {
    writes += 1;
    const error = new Error("Another user saved changes.");
    error.status = 409;
    throw error;
  });
  app.change("Keep this draft");
  assert.equal(await app.manager.flush(), false);
  app.change("Keep this too");
  assert.equal(await app.manager.flush(), false);
  assert.equal(app.manager.dirty, true);
  assert.equal(app.manager.conflict, true);
  assert.equal(writes, 1);
  app.manager.reset();
});

test("a failed save keeps the draft and can be retried", async () => {
  let writes = 0;
  const app = setup(async () => {
    writes += 1;
    if (writes === 1) throw new Error("Server unavailable");
    return { version: 2 };
  });
  app.change("Keep on failure");
  assert.equal(await app.manager.flush(), false);
  assert.equal(app.manager.dirty, true);
  assert.equal(await app.manager.flush(), true);
  assert.equal(app.manager.dirty, false);
  app.manager.reset();
});

test("an empty title blocks saving and leaves changes unsaved", async () => {
  let writes = 0;
  const app = setup(async () => { writes += 1; return { version: 2 }; });
  app.change("   ");
  assert.equal(await app.manager.flush(), false);
  assert.equal(writes, 0);
  assert.equal(app.manager.dirty, true);
  assert.match(app.errors[0], /title/);
  app.manager.reset();
});

test("switching documents is rejected while a save is pending", async () => {
  let finish;
  const app = setup(() => new Promise((resolve) => { finish = resolve; }));
  app.change("Saving");
  const saving = app.manager.save();
  assert.throws(() => app.manager.reset(), /Wait/);
  finish({ version: 2 });
  await saving;
  app.manager.reset();
  assert.equal(app.manager.dirty, false);
});

======================================================================
FILE: tests/frontend/view.test.js
======================================================================
import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseHTML } from "linkedom";
import { state } from "../../static/js/state.js";
import { renderDocuments, showDocument, setBusy, resetFilters } from "../../static/js/view.js";

const html = readFileSync(new URL("../../static/index.html", import.meta.url), "utf8");
const owned = { id: 1, title: "My plan", owner_id: 1, owner_name: "Ahmed Ali", updated_at: "2026-11-17T12:00:00Z", content: { ops: [{ insert: "Hello team\n" }] } };
const shared = { ...owned, id: 2, title: "Team review", owner_id: 2, owner_name: "Sara Chen" };

beforeEach(() => {
  globalThis.document = parseHTML(html).document;
  Object.assign(state, { users: [], documents: [owned, shared], current: owned, userId: 1, filter: "all", busy: false });
  document.getElementById("search").value = "";
});

test("document records render as clickable items with owned and shared labels", () => {
  renderDocuments();
  const buttons = [...document.querySelectorAll(".document-item")];
  assert.deepEqual(buttons.map((button) => button.dataset.documentId), ["1", "2"]);
  assert.match(buttons[0].textContent, /Owned by you/);
  assert.match(buttons[1].textContent, /Shared by Sara/);
  assert.equal(buttons[0].getAttribute("aria-current"), "page");
  assert.equal(document.getElementById("document-count").textContent, "2");
});

test("search and the shared filter return only matching documents", () => {
  state.filter = "shared";
  document.getElementById("search").value = "review";
  renderDocuments();
  assert.equal(document.querySelectorAll(".document-item").length, 1);
  assert.equal(document.querySelector(".file-title").textContent, "Team review");
  document.getElementById("search").value = "missing";
  renderDocuments();
  assert.equal(document.querySelectorAll(".document-item").length, 0);
  assert.match(document.querySelector(".list-empty").textContent, /No matching/);
});

test("document titles are rendered as text and cannot inject HTML", () => {
  state.documents = [{ ...owned, title: '<img src=x onerror="alert(1)">' }];
  renderDocuments();
  assert.equal(document.querySelector(".file-title").textContent, '<img src=x onerror="alert(1)">');
  assert.equal(document.querySelector("#document-list img"), null);
});

test("shared documents show editor access and hide owner-only sharing", () => {
  let received;
  state.current = shared;
  const editor = { setContents: (content) => { received = content; }, getText: () => "Hello team\n" };
  showDocument(editor);
  assert.equal(document.getElementById("ownership").textContent, "Shared with you");
  assert.equal(document.getElementById("share-document").hidden, true);
  assert.equal(document.getElementById("word-count").textContent, "2 words");
  assert.deepEqual(received, shared.content);
});

test("busy navigation disables document switching until it finishes", () => {
  let enabled = true;
  const editor = { enable: (value) => { enabled = value; } };
  setBusy(editor, true);
  assert.equal(enabled, false);
  assert.equal(document.getElementById("user-select").disabled, true);
  assert.equal(document.querySelector(".document-item").disabled, true);
  setBusy(editor, false);
  assert.equal(enabled, true);
  assert.equal(document.getElementById("user-select").disabled, false);
});

test("creating a document can reset filters so the owned file is visible", () => {
  state.filter = "shared";
  document.getElementById("search").value = "old search";
  resetFilters();
  renderDocuments();
  assert.equal(state.filter, "all");
  assert.equal(document.getElementById("search").value, "");
  assert.equal(document.querySelectorAll(".document-item").length, 2);
  assert.equal(document.querySelector('[data-filter="all"]').classList.contains("active"), true);
});

======================================================================
FILE: tests/test_app.py
======================================================================
import tempfile
import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app
from app.config import MAX_UPLOAD_BYTES

EMPTY_CONTENT = {"ops": [{"insert": "\n"}]}


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "test.db"
        self.app = create_app(self.database_path)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.owner = {"X-User-Id": "1"}
        self.teammate = {"X-User-Id": "2"}
        self.stranger = {"X-User-Id": "3"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def create(self):
        response = self.client.post("/api/documents", headers=self.owner, json={"title": "Team plan"})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_create_edit_share_reopen_and_revoke(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        content = {"ops": [{"insert": "Important", "attributes": {"bold": True, "underline": True}},
                           {"insert": "\n", "attributes": {"header": 2}},
                           {"insert": "First item"}, {"insert": "\n", "attributes": {"list": "bullet"}}]}
        edited = self.client.put(path, headers=self.owner,
                                 json={"title": "Renamed plan", "content": content, "version": 1})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.teammate).status_code, 404)
        shared = self.client.post(path + "/shares", headers=self.owner, json={"user_id": 2})
        self.assertEqual(shared.status_code, 201)
        reopened = self.client.get(path, headers=self.teammate).json()
        self.assertEqual(reopened["content"], content)
        self.assertEqual(reopened["title"], "Renamed plan")
        self.assertEqual(reopened["owner_id"], 1)
        listing = self.client.get("/api/documents", headers=self.teammate).json()
        self.assertEqual([row["id"] for row in listing], [document["id"]])
        self.assertEqual(self.client.get(path, headers=self.stranger).status_code, 404)
        self.assertEqual(self.client.post(path + "/shares", headers=self.teammate,
                                          json={"user_id": 3}).status_code, 403)
        edit = self.client.put(path, headers=self.teammate,
                               json={"title": "Sara's update", "content": content, "version": 2})
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.owner).json()["title"], "Sara's update")
        self.assertEqual(self.client.delete(path + "/shares/2", headers=self.owner).status_code, 204)
        self.assertEqual(self.client.get(path, headers=self.teammate).status_code, 404)
        self.assertEqual(self.client.put(path, headers=self.teammate,
                                         json={"title": "Blocked", "content": content, "version": 3}).status_code, 404)

    def test_conflicting_save_does_not_overwrite(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        payload = {"title": "First edit", "content": EMPTY_CONTENT, "version": 1}
        self.assertEqual(self.client.put(path, headers=self.owner, json=payload).status_code, 200)
        payload["title"] = "Stale edit"
        self.assertEqual(self.client.put(path, headers=self.owner, json=payload).status_code, 409)
        self.assertEqual(self.client.get(path, headers=self.owner).json()["title"], "First edit")

    def test_import_text_and_validate_files(self):
        response = self.client.post("/api/documents/import", headers=self.owner,
                                    files={"file": ("notes.txt", b"\xef\xbb\xbfHello\r\nteam", "text/plain")})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["title"], "notes")
        self.assertEqual(response.json()["content"]["ops"][0]["insert"], "Hello\nteam\n")
        for filename, content in [("x.pdf", b"hello"), ("x.txt", b"\xff"), ("x.txt", b" "), ("x.txt", b"a\x00b")]:
            with self.subTest(filename=filename, content=content):
                result = self.client.post("/api/documents/import", headers=self.owner,
                                           files={"file": (filename, content)})
                self.assertEqual(result.status_code, 400)
        too_large = self.client.post("/api/documents/import", headers=self.owner,
                                     files={"file": ("x.txt", b"a" * (MAX_UPLOAD_BYTES + 1))})
        self.assertEqual(too_large.status_code, 413)

    def test_validation_and_unsupported_content(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        for content in [{"ops": [{"insert": {"image": "javascript:alert(1)"}}]},
                        {"ops": [{"insert": "x\n", "attributes": {"link": "javascript:alert(1)"}}]},
                        {"ops": [{"insert": "x"}]}, {"ops": []}]:
            with self.subTest(content=content):
                response = self.client.put(path, headers=self.owner,
                                            json={"title": "Valid", "content": content, "version": 1})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/documents", headers=self.owner,
                                          json={"title": "  "}).status_code, 422)
        self.assertEqual(self.client.get("/api/documents", headers={"X-User-Id": "100"}).status_code, 401)
        self.assertEqual(self.client.get("/api/documents").status_code, 422)

    def test_owner_validation_and_idempotent_sharing(self):
        document = self.create()
        path = f"/api/documents/{document['id']}/shares"
        self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 1}).status_code, 400)
        self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 999}).status_code, 404)
        for _ in range(2):
            self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 2}).status_code, 201)
        self.assertEqual(len(self.client.get(path, headers=self.owner).json()), 1)

    def test_persistence_across_application_restart(self):
        document = self.create()
        self.client.post(f"/api/documents/{document['id']}/shares", headers=self.owner, json={"user_id": 2})
        with TestClient(create_app(self.database_path)) as reopened:
            response = reopened.get(f"/api/documents/{document['id']}", headers=self.teammate)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["title"], "Team plan")

    def test_request_size_limit_and_static_app(self):
        response = self.client.post("/api/documents", headers=self.owner, content=b"x" * (2 * MAX_UPLOAD_BYTES + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertIn("folio", self.client.get("/").text)
        self.assertEqual(self.client.get("/static/vendor/quill.js").status_code, 200)


    def test_create_is_committed_before_success_response(self):
        app = self.app
        database_path = self.database_path
        visible_counts = []

        async def observe_response(scope, receive, send):
            async def observe_send(message):
                if message["type"] == "http.response.start" and message["status"] == 201:
                    with sqlite3.connect(database_path) as db:
                        visible_counts.append(db.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
                await send(message)
            await app(scope, receive, observe_send)

        with TestClient(observe_response) as client:
            response = client.post("/api/documents", headers=self.owner, json={"title": "Durable save"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(visible_counts, [1])

    def test_app_instances_use_separate_databases(self):
        document = self.create()
        other_path = Path(self.directory.name) / "other.db"
        with TestClient(create_app(other_path)) as other:
            self.assertEqual(other.get("/api/documents", headers=self.owner).json(), [])
            self.assertEqual(other.get(f"/api/documents/{document['id']}", headers=self.owner).status_code, 404)
        self.assertEqual(len(self.client.get("/api/documents", headers=self.owner).json()), 1)

    def test_simultaneous_saves_have_one_winner(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"

        def save(title):
            return self.client.put(path, headers=self.owner,
                                   json={"title": title, "content": EMPTY_CONTENT, "version": 1})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(save, ["First writer", "Second writer"]))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        saved = self.client.get(path, headers=self.owner).json()
        self.assertEqual(saved["version"], 2)
        winner = next(response.json() for response in responses if response.status_code == 200)
        self.assertEqual(saved["title"], winner["title"])

    def test_created_document_location_and_api_contract(self):
        response = self.client.post("/api/documents", headers=self.owner, json={"title": "Linked result"})
        self.assertEqual(response.headers["location"], f"/api/documents/{response.json()['id']}")
        self.assertEqual(self.client.get(response.headers["location"], headers=self.owner).status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/documents/{document_id}/shares", schema["paths"])
        self.assertEqual(schema["paths"]["/api/documents"]["get"]["tags"], ["Documents"])

    def test_frontend_module_imports_are_served(self):
        import re
        html = self.client.get("/").text
        self.assertIn('type="module" src="/static/js/app.js"', html)
        modules = ["app.js"]
        visited = set()
        while modules:
            name = modules.pop()
            if name in visited:
                continue
            visited.add(name)
            response = self.client.get("/static/js/" + name)
            self.assertEqual(response.status_code, 200, name)
            self.assertIn("javascript", response.headers["content-type"], name)
            modules.extend(re.findall(r'from "\./([^\"]+)"', response.text))
        self.assertGreaterEqual(len(visited), 8)


if __name__ == "__main__":
    unittest.main()

````
