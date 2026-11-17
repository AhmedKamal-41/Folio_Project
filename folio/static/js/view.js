import { $ } from "./dom.js";
import { state } from "./state.js";
import { updateWordCount } from "./editor.js";

export function renderDocuments() {
  const list = $("document-list");
  list.replaceChildren();
  const search = $("search").value.toLowerCase();
  const documents = state.documents.filter((document) => {
    const owned = document.owner_id === state.userId;
    return document.title.toLowerCase().includes(search) &&
      (state.filter === "all" || (state.filter === "owned" && owned) || (state.filter === "shared" && !owned));
  });
  $("document-count").textContent = documents.length;
  for (const item of documents) {
    const button = document.createElement("button");
    button.className = "document-item" + (item.id === state.current?.id ? " selected" : "");
    button.disabled = state.busy;
    if (item.id === state.current?.id) button.setAttribute("aria-current", "page");
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = "▤";
    const info = document.createElement("span");
    info.className = "file-info";
    const title = document.createElement("span");
    title.className = "file-title";
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "file-meta";
    const owner = item.owner_id === state.userId ? "Owned by you" : `Shared by ${item.owner_name.split(" ")[0]}`;
    meta.textContent = `${owner} · ${new Date(item.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
    info.append(title, meta);
    button.append(icon, info);
    button.dataset.documentId = item.id;
    list.append(button);
  }
  if (!documents.length) {
    const empty = document.createElement("p");
    empty.className = "list-empty";
    empty.textContent = state.documents.length ? "No matching documents." : "Your next idea belongs here. Create a document or import your notes.";
    list.append(empty);
  }
}

export function showDocument(editor) {
  const document = state.current;
  $("empty-state").hidden = Boolean(document);
  $("document-panel").hidden = !document;
  $("breadcrumb").textContent = document?.title || "Your documents";
  if (document) {
    const owned = document.owner_id === state.userId;
    $("document-title").value = document.title;
    editor.setContents(document.content, "silent");
    $("ownership").textContent = owned ? "Owned by you" : "Shared with you";
    $("owner-label").textContent = `${document.owner_name} · ${owned ? "Owner" : "You have editor access"}`;
    $("share-document").hidden = !owned;
    updateWordCount(editor);
  }
  renderDocuments();
}

export function setBusy(editor, value) {
  state.busy = value;
  for (const id of ["new-document", "empty-create", "import-document", "user-select", "save-document",
    "reload-document", "share-document", "document-title", "refresh-documents"]) {
    $(id).disabled = value;
  }
  editor.enable(!value && Boolean(state.current));
  renderDocuments();
}

export function resetFilters() {
  state.filter = "all";
  $("search").value = "";
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.classList.toggle("active", button.dataset.filter === "all");
  }
}

export function updateAccount() {
  const user = state.users.find((user) => user.id === state.userId);
  $("user-select").value = state.userId;
  $("avatar").textContent = user.name.split(" ").map((word) => word[0]).join("");
}

export function setSaveStatus(status) {
  const messages = {
    saved: "All changes saved",
    unsaved: "Unsaved changes",
    saving: "Saving…",
    error: "Save failed · try again",
    invalid: "A title is required",
    conflict: "Conflict · draft kept"
  };
  $("save-status").textContent = messages[status];
  $("conflict-banner").hidden = status !== "conflict";
}
