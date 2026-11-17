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
