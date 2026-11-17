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
keeps the unsaved draft and pauses retries; a Word (.docx) download, built
client-side from the Quill Delta via the `docx` library, provides a way to
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
The Word (.docx) download protects conflict recovery and preserves formatting,
but DOCX import is still out of scope.

Next: finish real-browser and deployed-persistence checks, record the video,
then add recovery drafts and a conflict comparison UI. Proper authentication
and a managed database would come before using the app for sensitive team data.

## Design references

- FastAPI routers: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Dependency cleanup before response: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- SQLite behavior: https://docs.python.org/3.12/library/sqlite3.html
