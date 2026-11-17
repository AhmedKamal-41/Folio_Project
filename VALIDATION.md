# Verification

Verified against the updated repository and its live Railway deployment.

## Automated tests

- **14 backend tests**: `python -m unittest discover -s tests -v`.
- **15 frontend tests**: `npm test` after `npm ci --ignore-scripts`.
- `git diff --check` passed for the deployment changes.

Backend tests exercise the actual HTTP application using temporary databases:
create/edit/reopen, sharing and teammate editing, owner-only sharing/deletion,
revocation, text and Word import, validation, request limits, stale/simultaneous
writes, database isolation, restart persistence, and commit before HTTP success.

Frontend tests cover real DOM rendering through LinkeDOM and asynchronous save
behavior: owned/shared labels, escaped titles, filters, owner controls, busy
navigation, serialized writes, typing during a save, conflict preservation,
retrying failures, title validation, and pausing a queued save before deletion.

## Live Chrome checks

At https://folio-production-3075c6e5.up.railway.app/:

- Created and renamed a document as Ahmed.
- Applied a heading, bold, italic, underline, and a bulleted list.
- Saved, refreshed, and reopened; formatting and content remained intact.
- Granted Sara access and verified the shared label and owner-only controls.
- Edited as Sara, saved, refreshed, and reopened the teammate update.
- Switched to uninvited Omar and verified the document was absent.
- Imported a Word file containing a heading, bold text, and a bullet.
- Downloaded a Word draft and parsed the resulting `.docx` with python-docx;
  its title, heading, bold run, and list paragraph were present.
- Redeployed the service successfully, reloaded the application, and reopened
  the same formatted plan with Sara's saved edit. The imported document also
  remained in the list, and the sharing dialog still listed Sara's access.

Screenshot: `docs/screenshots/live-folio.jpg` shows the saved plan after redeploy.

## Hosting

Railway successfully built the supplied Docker image and started Uvicorn on
port 8000. The `/api/health` deployment health check succeeded. The service
uses one replica and a persistent volume mounted at `/data`, with
`DATABASE_PATH=/data/folio.db`. GitHub `main` is connected for deployment.

## Not claimed

- Firefox/Safari, mobile layouts, and all keyboard shortcuts have not been
  manually verified in those environments.
- The live browser pass did not exercise every error branch or conflict
  combination; the automated suite covers stale saves and access revocation.
- No video has been recorded and no Google Drive submission folder has been
  assembled. These remain the candidate's final handoff tasks.
