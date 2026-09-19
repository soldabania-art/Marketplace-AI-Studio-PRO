import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {
  buildPublicSelectionHref,
  buildRegistrationIntent,
  normalizeRegistrationIntent,
  restorePublicSelection,
} from "../lib/publicSelection.mjs";

const landing = fs.readFileSync(
  new URL("../components/PublicLanding.js", import.meta.url),
  "utf8",
);
const register = fs.readFileSync(
  new URL("../app/register/page.js", import.meta.url),
  "utf8",
);
const login = fs.readFileSync(
  new URL("../app/login/page.js", import.meta.url),
  "utf8",
);
const forgotPassword = fs.readFileSync(
  new URL("../app/forgot-password/page.js", import.meta.url),
  "utf8",
);
const selection = fs.readFileSync(
  new URL("../lib/publicSelection.mjs", import.meta.url),
  "utf8",
);

test("D02 preserves the existing public authentication URLs", () => {
  assert.match(landing, /href=["']\/login["']/);
  assert.match(landing, /href:["']\/register["']/);
  assert.match(selection, /return `\/register\?/);
  assert.match(login, /href=["']\/forgot-password["']/);
  assert.match(login, /href=["']\/register["']/);
  assert.match(forgotPassword, /href=["']\/login["']/);
});

test("public selection is handed to registration as a request", () => {
  for (const parameter of ["plan", "channel", "stores", "modules"])
    assert.match(selection, new RegExp(`URLSearchParams\\(\\{[^}]*${parameter}`, "s"));

  for (const field of [
    "requested_plan",
    "active_channel",
    "marketplace_interest",
    "requested_stores",
    "requested_modules",
  ])
    assert.match(register, new RegExp(`${field}:`));

  assert.match(register, /normalizeRegistrationIntent\(params\)/);
  assert.match(register, /желаемый план, а не оплаченный или активный тариф/);
  assert.match(register, /интерес к запланированной интеграции/);

  assert.equal(
    buildRegistrationIntent({
      channel: "wb",
      modules: ["cards", "director"],
      stores: 3,
      plan: "pro",
      interest: "ozon",
    }),
    "/register?plan=pro&channel=wb&stores=3&modules=cards%2Cdirector&interest=ozon",
  );
});

test("registration query values are allowlisted and repeated modules are deduplicated", () => {
  const normalized = normalizeRegistrationIntent(new URLSearchParams(
    "plan=enterprise&channel=ozon&stores=-4&modules=cards,unknown,cards&modules=director,,cards&interest=unknown",
  ));

  assert.deepEqual(normalized, {
    plan: "trial",
    channel: "start",
    stores: "1",
    modules: ["cards", "director"],
    interest: "",
  });
  assert.deepEqual(
    normalizeRegistrationIntent(new URLSearchParams("plan=&channel=&stores=&modules=&interest=")),
    { plan: "trial", channel: "start", stores: "1", modules: [], interest: "" },
  );
  assert.deepEqual(Object.keys(normalized).sort(), ["channel", "interest", "modules", "plan", "stores"]);
});

test("registration can return to the same normalized public selection", () => {
  const registrationHref = buildRegistrationIntent({
    channel: "wb",
    modules: ["cards", "director"],
    stores: 10,
    plan: "business",
    interest: "yandex",
  });
  const normalized = normalizeRegistrationIntent(
    new URL(registrationHref, "https://example.test").searchParams,
  );

  assert.equal(
    buildPublicSelectionHref(normalized),
    "/?plan=business&channel=wb&stores=10&modules=cards%2Cdirector&interest=yandex#bundle",
  );
  assert.deepEqual(restorePublicSelection(new URL(buildPublicSelectionHref(normalized), "https://example.test").searchParams), {
    channel: "yandex",
    modules: ["cards", "director"],
    stores: 10,
  });
  assert.match(register, /href=\{selectionHref\}/);
  assert.match(landing, /restorePublicSelection\(params\)/);
});

test("public selection does not grant access or mutate entitlements", () => {
  assert.doesNotMatch(landing, /fetch\s*\(/);
  assert.doesNotMatch(landing, /localStorage|sessionStorage|document\.cookie/);
  assert.doesNotMatch(landing, /grant_access|setEntitlement|setPermission|setMembership/i);
  assert.doesNotMatch(register, /grant_access|setEntitlement|setPermission|setMembership/i);
  assert.match(landing, /Выбор не выдаёт права доступа/);
  assert.match(landing, /Публичный выбор — не полномочие/);
});

test("future marketplaces remain explicit registration interests", () => {
  for (const marketplace of ["Ozon", "Яндекс Маркет", "Kaspi.kz", "Uzum Market"])
    assert.match(selection, new RegExp(marketplace.replace(".", "\\.")));
  for (const interest of ["ozon", "yandex", "kaspi", "uzum"])
    assert.equal(normalizeRegistrationIntent(new URLSearchParams(`interest=${interest}`)).interest, interest);
  assert.match(register, /marketplace_interest:\s*interest\s*\|\|\s*null/);
});

test("D02 uses accepted direction B and honest capability labels", () => {
  const publicCss = fs.readFileSync(
    new URL("../app/public-landing.css", import.meta.url),
    "utf8",
  );
  for (const token of ["#100d29", "#f0526c", "#43d8c6", "#c9ff68"])
    assert.match(publicCss, new RegExp(token));
  assert.match(landing, /DECISION TRACE/);
  assert.match(selection, /Wildberries[\s\S]*Можно настроить после входа/);
  for (const marketplace of ["Ozon", "Яндекс Маркет", "Kaspi.kz", "Uzum Market"])
    assert.match(selection, new RegExp(`${marketplace.replace(".", "\\.")}[\\s\\S]*Запланировано`));
  assert.doesNotMatch(landing, /НАБЛЮДАЕМЫЙ РАСХОД|результат клиента|клиент заработал/i);
  assert.doesNotMatch(landing, /реализованн(?:ый|ого) web-контур/i);
  assert.match(landing, /интерес к запланированной интеграции/);
  assert.match(landing, /PRO — желаемый план, не оплата и не активный тариф/);
  assert.match(publicCss, /:focus-visible/);
  assert.match(publicCss, /prefers-reduced-motion:reduce/);
  assert.match(publicCss, /@media\(max-width:760px\)/);
});

test("public styles stay isolated from workspace and auth screens", () => {
  const publicCss = fs.readFileSync(
    new URL("../app/public-landing.css", import.meta.url),
    "utf8",
  );
  assert.match(publicCss, /^\.publicLanding\{/);
  assert.doesNotMatch(publicCss, /(^|})\s*(html|body|main|a|button|\.shell|\.workspace|\.authShell)(?=[\s,{])/m);
  for (const source of [register, login, forgotPassword])
    assert.doesNotMatch(source, /public-landing\.css|className=["'`]public/);
});
