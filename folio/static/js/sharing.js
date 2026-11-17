import { api } from "./api.js";
import { $, notify } from "./dom.js";
import { state } from "./state.js";

export function initializeSharing(documents) {
  let busy = false;

  function setBusy(value) {
    busy = value;
    for (const button of $("share-dialog").querySelectorAll("button")) button.disabled = value;
    $("share-user").disabled = value;
    $("grant-access").disabled = value || !$("share-user").value;
  }

  async function render() {
    const shares = await api(`/documents/${state.current.id}/shares`);
    const owner = state.users.find((user) => user.id === state.current.owner_id);
    const list = $("share-list");
    list.replaceChildren();
    for (const user of [owner, ...shares]) {
      const row = document.createElement("div");
      row.className = "member";
      const name = document.createElement("span");
      name.textContent = user.name;
      const email = document.createElement("small");
      email.textContent = user.email;
      name.append(email);
      const role = document.createElement(user.id === owner.id ? "span" : "button");
      role.className = "member-role";
      role.textContent = user.id === owner.id ? "Owner" : "Remove access";
      if (user.id !== owner.id) role.dataset.userId = user.id;
      row.append(name, role);
      list.append(row);
    }
    const available = state.users.filter((user) => user.id !== owner.id && !shares.some((share) => share.id === user.id));
    $("share-user").replaceChildren(...available.map((user) => new Option(user.name, user.id)));
    if (!available.length) $("share-user").append(new Option("Everyone already has access", ""));
    setBusy(false);
  }

  async function changeAccess(action) {
    if (busy) return;
    setBusy(true);
    try {
      await action();
      await render();
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  $("share-document").addEventListener("click", () => documents.navigate(async () => {
    await render();
    $("share-dialog").showModal();
  }));
  $("close-share").addEventListener("click", () => $("share-dialog").close());
  $("share-dialog").addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
  $("grant-access").addEventListener("click", () => {
    const userId = Number($("share-user").value);
    changeAccess(async () => {
      await api(`/documents/${state.current.id}/shares`, {
        method: "POST", body: JSON.stringify({ user_id: userId })
      });
      notify("Editor access granted. Switch demo accounts to try it.");
    });
  });
  $("share-list").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-user-id]");
    if (!button) return;
    changeAccess(() => api(`/documents/${state.current.id}/shares/${button.dataset.userId}`, { method: "DELETE" }));
  });
}
