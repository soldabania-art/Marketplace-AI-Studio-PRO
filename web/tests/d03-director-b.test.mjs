import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {
  createDirectorMutationCoordinator,
  createDirectorRequestCoordinator,
  directorActionAvailability,
  directorViewFlags,
} from "../lib/directorView.mjs";

const component = fs.readFileSync(
  new URL("../components/DailyDirectorWorkspace.js", import.meta.url),
  "utf8",
);
const css = fs.readFileSync(new URL("../app/director/director.css", import.meta.url), "utf8");
const activeStore = fs.readFileSync(new URL("../lib/useActiveStore.js", import.meta.url), "utf8");
const directorView = fs.readFileSync(new URL("../lib/directorView.mjs", import.meta.url), "utf8");

const response = (payload, ok = true) => ({ ok, json: async () => payload });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

test("late Director response from the previous store is rejected", async () => {
  const requests = new Map();
  const coordinator = createDirectorRequestCoordinator((url, options) => {
    const storeId = new URL(url, "https://example.test").searchParams.get("store_id");
    const pending = deferred();
    requests.set(storeId, { ...pending, signal: options.signal });
    return pending.promise;
  });

  const first = coordinator.load("store-a");
  const second = coordinator.load("store-b");
  assert.equal(requests.get("store-a").signal.aborted, true);
  requests.get("store-a").resolve(response({ store_id: "store-a" }));
  assert.deepEqual(await first, { kind: "superseded", storeId: "store-a" });
  requests.get("store-b").resolve(response({ store_id: "store-b", actions: [] }));
  assert.equal((await second).data.store_id, "store-b");
});

test("Director rejects a mismatched store payload and exposes API errors", async () => {
  const mismatch = createDirectorRequestCoordinator(async () => response({ store_id: "another-store" }));
  assert.deepEqual(await mismatch.load("selected-store"), {
    kind: "error",
    storeId: "selected-store",
    error: "Director вернул данные другого магазина. Ответ отклонён.",
  });
  const failed = createDirectorRequestCoordinator(async () => response({ error: "Источник временно недоступен" }, false));
  assert.equal((await failed.load("selected-store")).error, "Источник временно недоступен");
});

test("A to B to A rejects the old mutation completion in every UI phase", async () => {
  const coordinator = createDirectorMutationCoordinator();
  const oldResponse = deferred();
  const state = {
    notice: "",
    refreshes: 0,
    actionBusy: "old-action-a",
    resumeConfirmation: "СТАРОЕ ПОДТВЕРЖДЕНИЕ",
  };

  coordinator.enterContext("store-a");
  const oldToken = coordinator.start("action");
  const oldCompletion = oldResponse.promise.then(({ message }) => {
    if (coordinator.accepts(oldToken)) {
      state.notice = message;
      state.refreshes += 1;
    }
    if (coordinator.finish(oldToken)) state.actionBusy = "";
  });

  coordinator.enterContext("store-b");
  coordinator.enterContext("store-a");
  const newToken = coordinator.start("action");
  state.actionBusy = "new-action-a";
  state.resumeConfirmation = "НОВОЕ ПОДТВЕРЖДЕНИЕ";
  oldResponse.resolve({ message: "Старый ответ A" });
  await oldCompletion;

  assert.deepEqual(state, {
    notice: "",
    refreshes: 0,
    actionBusy: "new-action-a",
    resumeConfirmation: "НОВОЕ ПОДТВЕРЖДЕНИЕ",
  });
  assert.equal(coordinator.accepts(newToken), true);
});

test("operation id rejects an older mutation within the same store generation", () => {
  const coordinator = createDirectorMutationCoordinator();
  coordinator.enterContext("store-a");
  const older = coordinator.start("action");
  const newer = coordinator.start("action");
  assert.equal(coordinator.accepts(older), false);
  assert.equal(coordinator.finish(older), false);
  assert.equal(coordinator.accepts(newer), true);
  assert.equal(coordinator.finish(newer), true);
  assert.equal(coordinator.accepts(newer), false);
});

test("an old STOP completion cannot clear a new confirmation after A to B to A", async () => {
  const coordinator = createDirectorMutationCoordinator();
  coordinator.enterContext("store-a");
  const oldControl = coordinator.start("control");
  coordinator.enterContext("store-b");
  coordinator.enterContext("store-a");
  coordinator.start("action");
  let confirmation = "НОВОЕ ПОДТВЕРЖДЕНИЕ";

  if (coordinator.accepts(oldControl)) confirmation = "";
  coordinator.finish(oldControl);
  assert.equal(confirmation, "НОВОЕ ПОДТВЕРЖДЕНИЕ");
});

test("isolated fixtures identify empty, degraded, read-only and STOP states", () => {
  const fixture = {
    actions: [],
    control: { stopped: true },
    sources: [
      { name: "catalog", state: "missing" },
      { name: "stocks", state: "stale" },
      { name: "feedbacks", state: "error" },
      { name: "sales_velocity_7d", state: "incomplete" },
    ],
  };
  assert.deepEqual(directorViewFlags(fixture, false), {
    empty: true,
    stopped: true,
    readOnly: true,
    missing: true,
    stale: true,
    incomplete: true,
    sourceError: true,
  });
});

test("unavailable actions stay manual and STOP does not disable allowed reads", () => {
  const manual = directorActionAvailability({
    status: "proposed",
    requires_approval: false,
    can_execute: false,
    execution_type: null,
  }, true);
  assert.equal(manual.canExecute, false);
  assert.match(manual.unavailableReason, /исполнителя нет/);

  const readSync = directorActionAvailability({
    status: "proposed",
    requires_approval: false,
    can_execute: true,
    execution_type: "read_sync",
  }, true);
  assert.equal(readSync.canExecute, true);
  assert.equal(directorViewFlags({ control: { stopped: true }, sources: [], actions: [] }, true).stopped, true);

  const viewer = directorActionAvailability({
    status: "proposed",
    requires_approval: true,
    can_execute: false,
  }, false);
  assert.equal(viewer.canDecide, false);
  assert.match(viewer.unavailableReason, /Только просмотр/);
});

test("working Director uses real contracts and keeps B styles isolated", () => {
  const runtime = component + directorView;
  for (const contract of [
    "/api/director?store_id=",
    "/api/director/actions/",
    "/api/director/control",
    "observed_effect_kopecks",
    "data?.store_id===storeId",
  ]) assert.match(runtime, new RegExp(contract.replace(/[/?]/g, "\\$&")));
  assert.match(activeStore, /canManageStore:Boolean\(activeWorkspace\?\.can_manage_stores\)/);
  assert.doesNotMatch(component, /Billing read-only|серверная policy|owner\/admin|workspace/);
  assert.match(component, /Статус рассчитан по срокам обновления каждого источника/);
  assert.match(component, /if\(!mutationCoordinator\.accepts\(token\)\)return/);
  assert.match(component, /if\(mutationCoordinator\.accepts\(token\)\)setNotice\(mutationError\.message\)/);
  assert.match(component, /clearConfirmation=mutationCoordinator\.accepts\(token\)/);
  assert.equal(component.match(/mutationCoordinator\.finish\(token\)/g)?.length, 3);
  assert.doesNotMatch(component, /18 420|146 300|12 840|демо-задач/i);
  assert.match(css, /^\.directorB\{/);
  assert.doesNotMatch(css, /(^|})\s*(html|body|\.shell|\.workspace|\.authShell)(?=[\s,{])/m);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(css, /@media\(max-width:680px\)/);
});
