# Walkthrough recording outline — about 4 minutes

Record the real application in a browser. Explain these points in your own words.

## 0:00–0:25 — Scope

“This is Folio, a small workspace for creating and sharing documents. I focused
on the complete writing and sharing flow within the assessment timebox.”

Show the account selector. Explain that the three identities are demo users.

## 0:25–1:20 — Create, format, and save

Create a document, rename it, and add text. Show bold, italic, underline, a
heading, and a list. Point to autosave. Refresh and reopen the saved document
to demonstrate persistence and formatting.

## 1:20–2:10 — Sharing

As Ahmed, grant Sara access. Switch to Sara, show the Shared badge, and edit.
Switch back to Ahmed to reopen the update. Show that Omar has no access.
Explain that the owner manages sharing and can remove access.

## 2:10–2:40 — Import

Import `samples/team-notes.txt` or a small Word file. Show its editable content
and **Download draft** Word export. Explain `.txt`/`.docx`, the 1 MB limit,
and that complex Word layouts, tables, and images are not preserved.

## 2:40–3:20 — Engineering choices

Explain the browser modules, feature routes/services, and SQLite flow, Delta JSON formatting, permission
checks, and the need for a persistent deployment volume. Demonstrate a two-tab
save conflict if time allows; explain that concurrent edits are not live-merged.

## 3:20–4:00 — Tradeoffs, tests, and AI

Show the backend and frontend tests. Briefly show the separated routes, services, and UI modules. Explain how AI helped implement and test the
code, what you reviewed or changed yourself, and any remaining limitations.
Be specific about what you actually checked; do not read unverified claims.
Mention real auth, live collaboration, comments, and history as scope cuts.
Show the live Railway URL and explain that the `/data` volume retains SQLite
data. Mention the 29 passing automated tests and the verified live flows.

Upload the recording to Loom, YouTube, Vimeo, or Google Drive with reviewer
access enabled. Put its real URL in `VIDEO_URL.txt` and `SUBMISSION.md`.
Paste the same URL into the assessment's required Video Submission Link field.
