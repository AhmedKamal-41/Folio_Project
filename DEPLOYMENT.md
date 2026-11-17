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
