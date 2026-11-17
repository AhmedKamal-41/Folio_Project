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
| `app/routes/documents.py` | Receives list/create/import/get/update/delete requests and calls document services. |
| `app/routes/sharing.py` | Receives grant/list/revoke sharing requests. |
| `app/routes/users.py` | Lists the three demo users. |
| `app/routes/health.py` | Checks database availability for hosting readiness. |
| `app/services/documents.py` | Reads/writes documents, checks access, detects stale saves, and enforces owner-only deletion. |
| `app/services/sharing.py` | Enforces owner-only sharing and grants or revokes editor access. |
| `app/services/imports.py` | Validates UTF-8 text and Word (.docx) files and turns them into a document payload. |

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
| `static/js/editor.js` | Initializes Quill, updates word counts, and downloads drafts as Word (.docx) files. |
| `static/js/view.js` | Renders the document list, ownership labels, account controls, and save status. |
| `static/js/autosave.js` | Debounces and serializes saves, tracks newer edits, and stops on conflicts. |
| `static/js/documents.js` | Handles create/open/import/delete/refresh/account switching and draft-safe navigation. |
| `static/js/sharing.js` | Renders sharing controls and grants or revokes access. |
| `static/vendor/` | Contains pinned Quill and Word-export distributions and their licenses. |

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
| `download_vendor.py` | Restores pinned Quill and docx assets with checksum verification if needed. |
| `Dockerfile`, `compose.yaml`, `railway.json` | Build, run, persist, and healthcheck the app. |
| `DEPLOYMENT.md` | Explains deployment and post-deployment verification. |
| `ARCHITECTURE.md`, `AI_WORKFLOW.md`, `VALIDATION.md` | Explain design, AI usage, and verification evidence. |
| `WALKTHROUGH.md`, `SUBMISSION.md`, URL files | Prepare the assessment submission. |
| `NEXT_STEPS.md` | Lists the remaining recording, Drive upload, and form submission steps. |

The generated SQLite database is `data/folio.db` locally or `/data/folio.db`
in Docker/Railway. It is not committed to source or included in the ZIP.
