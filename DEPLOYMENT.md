# Folio deployment

**Live URL:** https://folio-production-3075c6e5.up.railway.app/

The application is deployed on Railway from
`AhmedKamal-41/Folio_Project`, branch `main`. The Docker build and health check
completed successfully. Core live browser and redeploy-persistence checks are
recorded in `VALIDATION.md`.

## Current configuration

| Setting | Value |
|---|---|
| Project / service | `Folio` / `folio` |
| Environment | `production` |
| Source | GitHub `AhmedKamal-41/Folio_Project`, branch `main` |
| Build | Root `Dockerfile`; no frontend build step |
| Replicas / region | One replica / `us-west2` |
| Volume | `folio-data`, mounted at `/data` |
| Database | `DATABASE_PATH=/data/folio.db` |
| Application/domain port | `PORT=8000`, domain target port `8000` |
| Health check | `/api/health`, timeout 120 seconds |

The frontend and API share one origin. No separate frontend deployment,
manual seed command, API key, or CORS setup is required. Reviewers select
demo accounts in the app without passwords.

## Update the deployed app

1. Commit and push changes to this repository's `main` branch.
2. Open the Railway project and watch the `folio` deployment until it succeeds.
3. Open the live URL and check the affected workflow. Check `/api/health`.
4. Inspect Railway build/runtime logs if a release fails.

The repository includes GitHub Actions for Python and JavaScript tests. Run
the tests before pushing; the deployment source is connected directly to main.

## Recreate the deployment if needed

1. In Railway, create a service from this GitHub repository's `main` branch.
2. Use the root Dockerfile. `railway.json` specifies its path and health check.
3. Attach a persistent volume at `/data` and set
   `DATABASE_PATH=/data/folio.db` and `PORT=8000`.
4. Keep one replica and generate a public domain targeting port 8000.
5. Wait for a successful release, then test the editor and sharing flow.

Keep the existing volume to retain documents and shares. SQLite requires
this single-replica setup. Do not commit the database to the repository.

## Local Docker rehearsal

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Compose uses a named database volume and an HTTP
health check. The Docker image was built by Railway; local Docker Compose
execution has not been separately verified in this environment.

## Troubleshooting

| Symptom | Check |
|---|---|
| Build looks for a Node start script | Use the root Dockerfile as the build path. |
| App cannot open its database | Check the `/data` volume and writable database path. |
| Documents disappear after redeploy | Check that the database uses the existing attached volume. |
| App starts but the domain fails | Match `PORT` and the domain's target port. |
| Save returns 409 | Download the draft, reload the latest document, and reapply edits. |

For final delivery, follow `NEXT_STEPS.md`, record `WALKTHROUGH.md`, and fill
the video and Drive URLs. The mock identity selector is suitable for demo
data; real team use requires actual authentication.
