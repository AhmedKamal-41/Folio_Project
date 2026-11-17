import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state, rememberUserId } from "./state.js";
import { renderDocuments, showDocument, setBusy, resetFilters, updateAccount } from "./view.js";

export function createDocumentController(editor, saves) {
  function setDocument(document) {
    saves.reset();
    state.current = document;
    showDocument(editor);
  }

  async function navigate(action, save = true) {
    if (state.busy) return false;
    setBusy(editor, true);
    try {
      if (save && !await saves.flush()) return false;
      await action();
      return true;
    } catch (error) {
      notify(error.message, true);
      return false;
    } finally {
      setBusy(editor, false);
    }
  }

  async function load() {
    state.documents = await api("/documents");
    renderDocuments();
  }

  function open(id) {
    if (state.current?.id === id) return;
    return navigate(async () => setDocument(await api(`/documents/${id}`)));
  }

  async function create() {
    const created = await navigate(async () => {
      const document = await api("/documents", {
        method: "POST", body: JSON.stringify({ title: "Untitled document" })
      });
      state.documents.unshift(document);
      resetFilters();
      setDocument(document);
    });
    if (created) {
      $("document-title").focus();
      $("document-title").select();
    }
  }

  async function importFile(file) {
    if (!file) return;
    if (!/\.(txt|docx)$/i.test(file.name) || file.size > 1024 * 1024) {
      notify("Choose a UTF-8 .txt or Word (.docx) file under 1 MB.", true);
      return;
    }
    await navigate(async () => {
      const data = new FormData();
      data.append("file", file);
      const document = await api("/documents/import", { method: "POST", body: data });
      state.documents.unshift(document);
      resetFilters();
      setDocument(document);
      notify("Your notes are ready to edit.");
    });
  }

  async function switchUser(userId) {
    await navigate(async () => {
      const documents = await api("/documents", { userId });
      state.userId = userId;
      state.documents = documents;
      rememberUserId(userId);
      resetFilters();
      updateAccount();
      setDocument(null);
    });
    $("user-select").value = state.userId;
  }

  function remove(id) {
    const target = state.documents.find((document) => document.id === id);
    if (!target) return;
    if (!confirm(`Delete "${target.title}"? This cannot be undone.`)) return;
    return navigate(async () => {
      await api(`/documents/${id}`, { method: "DELETE" });
      state.documents = state.documents.filter((document) => document.id !== id);
      if (state.current?.id === id) setDocument(null);
      renderDocuments();
    }, false);
  }

  function reload() {
    return navigate(async () => {
      await saves.waitForPending();
      if (saves.dirty && !confirm("Discard your unsaved draft? Download a Word copy first if you need to keep it.")) return;
      setDocument(await api(`/documents/${state.current.id}`));
    }, false);
  }

  return { open, create, importFile, switchUser, reload, remove, load, navigate, refresh: () => navigate(load) };
}
