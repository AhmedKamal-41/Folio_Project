import test from "node:test";
import assert from "node:assert/strict";
import { setTimeout as wait } from "node:timers/promises";
import { createSaveManager } from "../../static/js/autosave.js";

function setup(write) {
  let draft = { id: 1, title: "Plan", content: { ops: [{ insert: "First draft\n" }] }, version: 1 };
  const statuses = [];
  const errors = [];
  const manager = createSaveManager({
    readSnapshot: () => structuredClone(draft),
    writeSnapshot: write,
    onSaved: (saved) => { draft.version = saved.version; },
    onStatus: (status) => statuses.push(status),
    onError: (error) => errors.push(error.message),
    delay: 60000
  });
  return { manager, statuses, errors, change: (title) => { draft.title = title; manager.changed(); } };
}

test("pausing a draft prevents a scheduled save without discarding its contents", async () => {
  let writes = 0;
  const manager = createSaveManager({
    readSnapshot: () => ({ title: "Keep this draft" }),
    writeSnapshot: async () => { writes += 1; return { version: 2 }; },
    onSaved: () => {}, onStatus: () => {}, onError: () => {}, delay: 5
  });
  manager.changed();
  manager.pause();
  await wait(20);
  assert.equal(writes, 0);
  assert.equal(manager.dirty, true);
  manager.reset();
});

test("flush saves a valid changed document and clears unsaved state", async () => {
  const writes = [];
  const app = setup(async (snapshot) => { writes.push(snapshot); return { version: snapshot.version + 1 }; });
  app.change("Updated plan");
  assert.equal(await app.manager.flush(), true);
  assert.equal(writes[0].title, "Updated plan");
  assert.equal(app.manager.dirty, false);
  assert.equal(app.statuses.at(-1), "saved");
  app.manager.reset();
});

test("typing during an in-flight save is saved afterward with the new version", async () => {
  let finishFirst;
  const writes = [];
  const app = setup((snapshot) => {
    writes.push(snapshot);
    if (writes.length === 1) return new Promise((resolve) => { finishFirst = resolve; });
    return Promise.resolve({ version: snapshot.version + 1 });
  });
  app.change("First edit");
  const saving = app.manager.save();
  app.change("Second edit");
  finishFirst({ version: 2 });
  await saving;
  assert.equal(app.manager.dirty, true);
  assert.equal(await app.manager.flush(), true);
  assert.deepEqual(writes.map((snapshot) => [snapshot.title, snapshot.version]), [["First edit", 1], ["Second edit", 2]]);
  app.manager.reset();
});

test("overlapping save requests do not duplicate an in-flight write", async () => {
  let finish;
  let writes = 0;
  const app = setup(() => { writes += 1; return new Promise((resolve) => { finish = resolve; }); });
  app.change("An edit");
  const first = app.manager.save();
  const second = app.manager.save();
  assert.equal(writes, 1);
  finish({ version: 2 });
  await Promise.all([first, second]);
  assert.equal(app.manager.dirty, false);
  app.manager.reset();
});

test("a version conflict keeps the draft and stops automatic retries", async () => {
  let writes = 0;
  const app = setup(async () => {
    writes += 1;
    const error = new Error("Another user saved changes.");
    error.status = 409;
    throw error;
  });
  app.change("Keep this draft");
  assert.equal(await app.manager.flush(), false);
  app.change("Keep this too");
  assert.equal(await app.manager.flush(), false);
  assert.equal(app.manager.dirty, true);
  assert.equal(app.manager.conflict, true);
  assert.equal(writes, 1);
  app.manager.reset();
});

test("a failed save keeps the draft and can be retried", async () => {
  let writes = 0;
  const app = setup(async () => {
    writes += 1;
    if (writes === 1) throw new Error("Server unavailable");
    return { version: 2 };
  });
  app.change("Keep on failure");
  assert.equal(await app.manager.flush(), false);
  assert.equal(app.manager.dirty, true);
  assert.equal(await app.manager.flush(), true);
  assert.equal(app.manager.dirty, false);
  app.manager.reset();
});

test("an empty title blocks saving and leaves changes unsaved", async () => {
  let writes = 0;
  const app = setup(async () => { writes += 1; return { version: 2 }; });
  app.change("   ");
  assert.equal(await app.manager.flush(), false);
  assert.equal(writes, 0);
  assert.equal(app.manager.dirty, true);
  assert.match(app.errors[0], /title/);
  app.manager.reset();
});

test("switching documents is rejected while a save is pending", async () => {
  let finish;
  const app = setup(() => new Promise((resolve) => { finish = resolve; }));
  app.change("Saving");
  const saving = app.manager.save();
  assert.throws(() => app.manager.reset(), /Wait/);
  finish({ version: 2 });
  await saving;
  app.manager.reset();
  assert.equal(app.manager.dirty, false);
});
