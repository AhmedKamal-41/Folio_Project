# AI workflow note

Tool used: ChatGPT / Codex for implementation, review, documentation, and tests.
The assistant reviewed my Python solutions to use clear names, explicit control
flow, and focused functions as a reference for the coding style.

## Human direction

I asked for the code to be separated into professional, understandable files
while keeping a straightforward coding style. The refactor follows that
instruction: routes, services, schemas, persistence, and browser features have
separate responsibilities. I will review and run the final code before submission.

## Where AI helped

AI translated the requirements into a bounded create/edit/import/share flow,
implemented the API and browser code, separated the original larger files,
and generated tests and written setup/architecture notes.

## Output changed or rejected

- Replaced the all-in-one backend with a small application entry point and
  feature modules. Split frontend API, autosave, documents, sharing, and rendering.
- Fixed a document-list bug where a variable named `document` shadowed the
  browser DOM object. A rendering regression test now covers populated lists.
- Added an application factory for isolated test databases and ensured a
  successful response is sent after transaction commit.
- Kept version-checked saves and added tests for simultaneous writes and typing
  during a pending save. Added a plain-text draft download for conflict recovery.
- Chose Quill/Delta instead of hand-written rich-text commands/raw HTML storage.
- Kept real auth, live merging, comments, and DOCX support outside the timebox.

## Verification and remaining work

Backend tests exercise the actual HTTP application with temporary databases.
Frontend tests exercise save races and DOM rendering using LinkeDOM. They are
not a substitute for browser verification of the Quill toolbar and layout.
See `VALIDATION.md` for exact counts and what was actually run.

A local Chromium launch was unavailable earlier. Live deployment, real-browser
checks, recording, and the Google Drive submission are still pending. I will
only claim these after completing them and will explain the changes I personally
reviewed in my walkthrough.
