# AI workflow note

Tool used: ChatGPT / Codex for implementation, review, tests, documentation,
and deployment assistance. AI also operated a real Chrome browser to verify
the deployed application.

## Human direction

I chose a focused document editor and asked for clear names, explicit control
flow, small functions, and separate files. I rejected keeping the entire app
in one main file. The resulting structure separates routes, services,
validation, persistence, and browser features while staying straightforward.

The updated project adds Word import/export and owner-only deletion. I asked
the assistant to deploy the latest GitHub version and complete the remaining
written handoff. I still need to review the final changes and record my own
walkthrough before submitting.

## Where AI materially helped

- Converted the requirements into a bounded create/edit/import/share workflow.
- Implemented and organized backend and browser modules.
- Generated regression tests for access rules, persistence, and save races.
- Reviewed the changed repository, corrected deployment configuration, and
  deployed its Docker image with persistent storage on Railway.
- Drafted setup, architecture, validation, and submission documents.

## Output changed or rejected

- Replaced the original large backend with a small entry point and feature
  modules; separated frontend API, autosave, documents, sharing, and rendering.
- Used Quill Delta storage and server validation instead of accepting raw HTML.
- Added version checks and serialized saves to avoid silently overwriting
  newer edits. A Word download preserves a draft before conflict recovery.
- Corrected Railway configuration to use the supported Dockerfile path field.
- Fixed a deletion/autosave race by waiting for in-flight writes and pausing
  the queued write before removing the open document; added a regression test.
- Kept real login, live merging, comments, and history outside this scope.

## Verification and limits

All 14 backend and 15 frontend tests passed. Backend tests use actual HTTP
requests against isolated temporary databases. Frontend tests exercise DOM
rendering and asynchronous saves. Railway built the image and passed the
health check. A live Chrome pass verified formatting, saving/reopening,
sharing, teammate edits, Word import, and Word download. The downloaded file
was parsed separately to confirm its heading, bold text, and list paragraph.
Documents and sharing also survived a successful Railway redeploy.

`VALIDATION.md` distinguishes completed checks from remaining coverage.
AI assistance does not substitute for my understanding: the recording should
explain the decisions and changes I have personally reviewed. The video and
Google Drive submission are still pending; no fabricated links are included.
