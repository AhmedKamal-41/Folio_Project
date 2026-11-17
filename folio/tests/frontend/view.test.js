import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseHTML } from "linkedom";
import { state } from "../../static/js/state.js";
import { renderDocuments, showDocument, setBusy, resetFilters } from "../../static/js/view.js";

const html = readFileSync(new URL("../../static/index.html", import.meta.url), "utf8");
const owned = { id: 1, title: "My plan", owner_id: 1, owner_name: "Ahmed Ali", updated_at: "2026-11-17T12:00:00Z", content: { ops: [{ insert: "Hello team\n" }] } };
const shared = { ...owned, id: 2, title: "Team review", owner_id: 2, owner_name: "Sara Chen" };

beforeEach(() => {
  globalThis.document = parseHTML(html).document;
  Object.assign(state, { users: [], documents: [owned, shared], current: owned, userId: 1, filter: "all", busy: false });
  document.getElementById("search").value = "";
});

test("document records render as clickable items with owned and shared labels", () => {
  renderDocuments();
  const buttons = [...document.querySelectorAll(".document-item")];
  assert.deepEqual(buttons.map((button) => button.dataset.documentId), ["1", "2"]);
  assert.match(buttons[0].textContent, /Owned by you/);
  assert.match(buttons[1].textContent, /Shared by Sara/);
  assert.equal(buttons[0].getAttribute("aria-current"), "page");
  assert.equal(document.getElementById("document-count").textContent, "2");
});

test("search and the shared filter return only matching documents", () => {
  state.filter = "shared";
  document.getElementById("search").value = "review";
  renderDocuments();
  assert.equal(document.querySelectorAll(".document-item").length, 1);
  assert.equal(document.querySelector(".file-title").textContent, "Team review");
  document.getElementById("search").value = "missing";
  renderDocuments();
  assert.equal(document.querySelectorAll(".document-item").length, 0);
  assert.match(document.querySelector(".list-empty").textContent, /No matching/);
});

test("document titles are rendered as text and cannot inject HTML", () => {
  state.documents = [{ ...owned, title: '<img src=x onerror="alert(1)">' }];
  renderDocuments();
  assert.equal(document.querySelector(".file-title").textContent, '<img src=x onerror="alert(1)">');
  assert.equal(document.querySelector("#document-list img"), null);
});

test("shared documents show editor access and hide owner-only sharing", () => {
  let received;
  state.current = shared;
  const editor = { setContents: (content) => { received = content; }, getText: () => "Hello team\n" };
  showDocument(editor);
  assert.equal(document.getElementById("ownership").textContent, "Shared with you");
  assert.equal(document.getElementById("share-document").hidden, true);
  assert.equal(document.getElementById("word-count").textContent, "2 words");
  assert.deepEqual(received, shared.content);
});

test("busy navigation disables document switching until it finishes", () => {
  let enabled = true;
  const editor = { enable: (value) => { enabled = value; } };
  setBusy(editor, true);
  assert.equal(enabled, false);
  assert.equal(document.getElementById("user-select").disabled, true);
  assert.equal(document.querySelector(".document-item").disabled, true);
  setBusy(editor, false);
  assert.equal(enabled, true);
  assert.equal(document.getElementById("user-select").disabled, false);
});

test("creating a document can reset filters so the owned file is visible", () => {
  state.filter = "shared";
  document.getElementById("search").value = "old search";
  resetFilters();
  renderDocuments();
  assert.equal(state.filter, "all");
  assert.equal(document.getElementById("search").value, "");
  assert.equal(document.querySelectorAll(".document-item").length, 2);
  assert.equal(document.querySelector('[data-filter="all"]').classList.contains("active"), true);
});
