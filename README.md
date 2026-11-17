# Folio

A focused document workspace: create, format, rename, save, import, and share.
Built with FastAPI, SQLite, vanilla JavaScript modules, and Quill 2.0.3.

**Live demo:** [Open Folio](https://folio-production-3075c6e5.up.railway.app/).
Choose a demo account in the top-left selector; no password is required.

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
on startup. Editor and Word-export assets are included in the repository.
Run `python download_vendor.py` only if those bundled assets need restoring.

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
10. Import a small Word `.docx` file, then use **Download draft** to export it.
11. Create a throwaway document and use its delete control as the owner.

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
editor. Use **Download draft** to save a Word (.docx) copy, with formatting
preserved, before choosing **Reload latest** and reapplying your edits.
Drafts are not backed up offline; keep the tab open until a save succeeds or
you have downloaded a copy.

To demonstrate a conflict, open the same saved document in two tabs. Save a
change in one, then edit and save the older copy in the other. There is no
live merging, live cursor sharing, or version-history feature.

## Import limits

UTF-8 `.txt` or Word `.docx`, up to 1 MB and fewer than 100,000 characters.
Empty files, null bytes, invalid encodings, and other extensions are rejected.
A `.txt` file becomes plain editable text. A `.docx` file keeps paragraph-level
bold, italic, underline, headings (Heading 1-3), and bullet/numbered lists;
tables, images, and other styles are dropped since the editor does not support
them. Original binary files are not retained. Rich documents support up to
100,000 characters including the final newline and up to 5,000 text
operations. Full request bodies are limited to 2 MB.

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

The verified suite contains **14 backend tests and 15 frontend tests**.
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

The live application is deployed on Railway from this repository's `main`
branch with persistent storage. See `VALIDATION.md` for completed checks.
The remaining handoff is to record the walkthrough and assemble the Google
Drive folder. Follow **NEXT_STEPS.md**, then replace the pending video and
Drive links in `SUBMISSION.md`. The walkthrough is not recorded yet.

## References

- FastAPI modular applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Quill editor: https://quilljs.com/docs/quickstart/
- Quill's BSD license is included under `static/vendor/QUILL-LICENSE.txt`.
