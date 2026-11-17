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
