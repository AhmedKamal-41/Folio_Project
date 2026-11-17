export function createSaveManager({ readSnapshot, writeSnapshot, onSaved, onStatus, onError, delay = 900 }) {
  let revision = 0;
  let savedRevision = 0;
  let pending = null;
  let timer = null;
  let conflict = false;

  function isDirty() {
    return revision !== savedRevision;
  }

  function schedule() {
    clearTimeout(timer);
    if (!conflict) timer = setTimeout(save, delay);
  }

  function changed() {
    revision += 1;
    onStatus(conflict ? "conflict" : "unsaved");
    schedule();
  }

  async function save() {
    clearTimeout(timer);
    if (pending) return pending;
    if (!isDirty()) return true;
    if (conflict) return false;
    const snapshot = readSnapshot();
    if (!snapshot.title.trim()) {
      onStatus("invalid");
      onError(new Error("Give your document a title before saving."));
      return false;
    }
    snapshot.title = snapshot.title.trim();
    const savingRevision = revision;
    onStatus("saving");
    pending = (async () => {
      try {
        const saved = await writeSnapshot(snapshot);
        onSaved(saved, snapshot);
        savedRevision = savingRevision;
        onStatus(isDirty() ? "unsaved" : "saved");
        if (isDirty()) schedule();
        return true;
      } catch (error) {
        conflict = error.status === 409;
        onStatus(conflict ? "conflict" : "error");
        onError(error);
        return false;
      } finally {
        pending = null;
      }
    })();
    return pending;
  }

  async function flush() {
    if (pending && !await pending) return false;
    while (isDirty()) {
      if (!await save()) return false;
    }
    return true;
  }

  function reset() {
    if (pending) throw new Error("Wait for the current save before changing documents.");
    clearTimeout(timer);
    revision = 0;
    savedRevision = 0;
    conflict = false;
    onStatus("saved");
  }

  return {
    changed, save, flush, reset,
    waitForPending: () => pending || Promise.resolve(true),
    get dirty() { return isDirty(); },
    get saving() { return Boolean(pending); },
    get conflict() { return conflict; }
  };
}
