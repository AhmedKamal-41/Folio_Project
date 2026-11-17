import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state, storedUserId } from "./state.js";
import { createEditor, downloadDraft, updateWordCount } from "./editor.js";
import { createSaveManager } from "./autosave.js";
import { createDocumentController } from "./documents.js";
import { initializeSharing } from "./sharing.js";
import { renderDocuments, setBusy, updateAccount, setSaveStatus } from "./view.js";

let saves;
const editor = createEditor(markChanged);
saves = createSaveManager({
  readSnapshot: () => ({
    id: state.current.id,
    title: $("document-title").value,
    content: editor.getContents(),
    version: state.current.version
  }),
  writeSnapshot: ({ id, ...payload }) => api(`/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  onSaved: (saved) => {
    state.current.version = saved.version;
    state.current.title = saved.title;
    state.current.updated_at = saved.updated_at;
    state.documents = state.documents.map((document) => document.id === saved.id ? saved : document);
    $("breadcrumb").textContent = saved.title;
    renderDocuments();
  },
  onStatus: setSaveStatus,
  onError: (error) => notify(error.message, true)
});
const documents = createDocumentController(editor, saves);
initializeSharing(documents);

function markChanged() {
  if (!state.current || state.busy) return;
  saves.changed();
  updateWordCount(editor);
}

$("new-document").addEventListener("click", documents.create);
$("empty-create").addEventListener("click", documents.create);
$("document-title").addEventListener("input", markChanged);
$("save-document").addEventListener("click", () => { if (!state.busy) saves.flush(); });
$("reload-document").addEventListener("click", documents.reload);
$("download-draft").addEventListener("click", () => downloadDraft(editor).catch((error) => notify(`Could not create the Word document: ${error.message}`, true)));
$("refresh-documents").addEventListener("click", documents.refresh);
$("search").addEventListener("input", renderDocuments);
$("document-list").addEventListener("click", (event) => {
  const deleteButton = event.target.closest("button[data-delete-id]");
  if (deleteButton) {
    documents.remove(Number(deleteButton.dataset.deleteId));
    return;
  }
  const openButton = event.target.closest("button[data-document-id]");
  if (openButton) documents.open(Number(openButton.dataset.documentId));
});
for (const button of document.querySelectorAll("[data-filter]")) button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
  renderDocuments();
});
$("user-select").addEventListener("change", (event) => documents.switchUser(Number(event.target.value)));
$("import-document").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  documents.importFile(file);
});
window.addEventListener("beforeunload", (event) => {
  if (saves.dirty || saves.saving) { event.preventDefault(); event.returnValue = ""; }
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    if (!state.busy) saves.flush();
  }
});

async function initialize() {
  setBusy(editor, true);
  try {
    state.users = await api("/users");
    const stored = storedUserId();
    state.userId = state.users.some((user) => user.id === stored) ? stored : 1;
    $("user-select").replaceChildren(...state.users.map((user) => new Option(user.name, user.id)));
    updateAccount();
    await documents.load();
  } catch (error) {
    notify(`Could not load your workspace: ${error.message}`, true);
  } finally {
    setBusy(editor, false);
  }
}
initialize();
