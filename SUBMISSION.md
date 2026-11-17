# Folio — Ahmed Ali

Folio is a lightweight document workspace built with FastAPI, SQLite,
vanilla JavaScript modules, and Quill. The application is deployed and its
core browser workflows have been verified. The recording and Drive folder
still need their actual links before submitting this assessment.

## Review links

- Google Drive folder: **PENDING — upload the materials and paste the folder URL.**
- Live application: https://folio-production-3075c6e5.up.railway.app/
- Source code: https://github.com/AhmedKamal-41/Folio_Project
- Walkthrough video: **PENDING — record 3–5 minutes and paste the video URL.**

## Included

- Create, rename, rich-text editing, autosave/manual save, and reopening.
- Bold, italic, underline, headings, and bulleted/numbered lists.
- UTF-8 `.txt` and Word `.docx` import, with visible 1 MB limits and validation.
- Word `.docx` draft download that preserves supported formatting.
- Owner-controlled editor sharing, owned/shared indicators, and revocation.
- Owner-only deletion and version-checked saves to prevent stale overwrites.
- Modular backend: application setup, routes, services, schemas, dependencies,
  middleware, configuration, and SQLite persistence.
- Browser modules for API calls, editor, documents, sharing, autosave, and rendering.
- 14 backend and 15 frontend automated tests; GitHub Actions workflow included.
- README, file guide, architecture note, AI workflow note, validation report,
  deployment guide, submission checklist, and recording outline.
- Dockerfile, Compose file, Railway configuration, and the live URL text file.
- Bundled Quill and Word-export assets, licenses, and a sample text import.
- A live product screenshot at `docs/screenshots/live-folio.jpg`.

## Demo accounts

Use the account selector: **Ahmed Ali** (ID 1), **Sara Chen** (ID 2), or
**Omar Hassan** (ID 3). No passwords, registration, or payment are required.
Create a document as Ahmed, share it with Sara, then switch to Sara to edit it.
Omar has no access unless the owner grants it.

Identity is simulated through `X-User-Id`; anyone can switch accounts. The
server applies document permissions to the selected identity. This is a demo
login model, not production authentication.

## Run locally

Requires Python 3.12+. From the project directory:

```bash
python -m venv .venv
```

Activate using the Windows PowerShell or macOS/Linux command in `README.md`, then:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Backend tests:
`python -m unittest discover -s tests -v`. Frontend tests require Node 22+:
`npm ci --ignore-scripts`, then `npm test`. There is no Node runtime build.

## Verification

All 29 automated tests passed. Railway built the Docker image and completed
its health check. Live Chrome checks covered formatting, saving/reopening,
sharing, teammate edits, Word import, and formatted Word download. Documents
and sharing survived a successful Railway redeploy. See `VALIDATION.md` for
evidence and the limits of these checks.

## Incomplete and intentionally omitted

The walkthrough video and reviewer-accessible Google Drive folder are not
created yet. Replace both pending links and `VIDEO_URL.txt` before submission.
Real login, live merging/cursors, comments, history, offline draft recovery,
and advanced sharing roles are omitted. Every share grants editor access.
Word import/export supports the editor's basic formatting; complex layouts,
tables, and images are not preserved. SQLite runs on one service replica.

## Next 2–4 hours

Add recoverable local drafts and a conflict comparison screen. Before using
the product with private team data, add real authentication and consider a
managed database for multiple application replicas.

## Final checklist

- [x] Deploy the repository on Railway with a persistent volume.
- [x] Fill `DEPLOYMENT_URL.txt` and the live link above.
- [x] Run automated tests and verify core flows in a real browser.
- [x] Verify documents and sharing survive a Railway redeploy.
- [x] Update architecture, AI workflow, and validation notes.
- [ ] Personally review the code and rehearse the main flow.
- [ ] Record/upload the walkthrough and fill `VIDEO_URL.txt` and the video link above.
- [ ] Upload the source and notes to one Google Drive folder with reviewer access.
- [ ] Replace the pending Drive link above.
- [ ] Paste the submission text and required video URL into the assessment form.
