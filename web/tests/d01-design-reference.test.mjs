import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const component = fs.readFileSync(
  new URL("../components/D01DesignReference.js", import.meta.url),
  "utf8",
);
const css = fs.readFileSync(
  new URL("../app/design-reference/d01.css", import.meta.url),
  "utf8",
);
const cookieConsent = fs.readFileSync(
  new URL("../app/components/CookieConsent.js", import.meta.url),
  "utf8",
);

test("D01 stays an isolated synthetic prototype without backend calls", () => {
  assert.match(component, /демонстрационные данные/);
  assert.doesNotMatch(component, /fetch\s*\(/);
  assert.match(component, /variant=control/);
  assert.match(component, /routeHref\(["']connect["']/);
  assert.match(component, /routeHref\(["']director["']/);
  assert.match(component, /platformHref\(["']connect["']/);
  assert.match(component, /platformHref\(["']director["']/);
});

test("D01 exposes two distinct studies and preserves the control prototype", () => {
  assert.match(component, /Монументальная точность/);
  assert.match(component, /Технологическая платформа/);
  assert.match(component, /Контроль/);
  assert.match(component, /MonumentalGraphic/);
  assert.match(component, /PlatformGraphic/);
  assert.match(component, /ArtDirection/);
  assert.match(component, /decisionStory\.map/);
  assert.match(component, /PlatformPrototype/);
  assert.match(component, /PlatformHome/);
  assert.match(component, /PlatformCapabilities/);
  assert.match(component, /PlatformConnect/);
  assert.match(component, /PlatformDirector/);
  for (const state of ["complete", "partial", "loading", "error", "unknown"])
    assert.match(component, new RegExp(`["']${state}["']`));
  assert.match(component, /Сумка-шоппер женская повседневная/);
  assert.match(component, /Доступно в демонстрации/);
  assert.match(component, /Запланировано/);
  assert.match(component, /НАБЛЮДАЕМЫЙ РАСХОД/);
  assert.match(component, /ПРИБЫЛЬ ЗА ПЕРИОД/);
  assert.match(component, /ЭФФЕКТ ДЕЙСТВИЯ/);
});

test("D01 includes keyboard focus, mobile and reduced-motion rules", () => {
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /@media\s*\(max-width:\s*700px\)/);
  assert.match(css, /\.studyMobile/);
  assert.match(css, /\.monumentalLedger/);
  assert.match(css, /\.platformOrbit/);
});

test("D01 gives A and B independent visual systems", () => {
  for (const token of [
    "--study-bg: #f2f2ee",
    "--study-accent: #cc321b",
    "--study-bg: #100d29",
    "--study-accent: #f0526c",
    "--study-signal: #43d8c6",
    "--study-accent-text: #a92c52",
  ]) {
    assert.match(css, new RegExp(token));
  }
});

test("D01 demo controls provide local reactions without writes", () => {
  assert.match(component, /setActionStatus\("approved"\)/);
  assert.match(component, /setActionStatus\("rejected"\)/);
  assert.match(component, /Локально, без запросов к WB/);
  assert.match(component, /Без записи в WB/);
  assert.match(component, /Демо-задача добавлена в контроль/);
});


test("selected direction B is the default connected route", () => {
  assert.match(component, /: "b";/);
  assert.match(component, /variant === "b".*PlatformPrototype/s);
  assert.match(component, /Доступно в демонстрации/);
  for (const marketplace of ["Ozon", "Яндекс Маркет", "Kaspi", "Uzum"])
    assert.match(component, new RegExp(marketplace));
  assert.match(component, /Будущие площадки показаны честно/);
  assert.match(component, /platformHref\("connect", "partial"\)/);
});

test("B Director separates evidence, money, action and execution control", () => {
  assert.match(component, /ПОДТВЕРЖДЁННАЯ ПРОБЛЕМА/);
  assert.match(component, /НАБЛЮДАЕМЫЙ РАСХОД/);
  assert.match(component, /ПРИБЫЛЬ ЗА ПЕРИОД/);
  assert.match(component, /ЭФФЕКТ ДЕЙСТВИЯ/);
  assert.match(component, /КОНТРОЛЬ ИСПОЛНЕНИЯ/);
  assert.match(component, /STOP доступен/);
  assert.match(component, /Слепая повторная отправка запрещена/);
  assert.match(component, /Демо-STOP включён локально/);
});

test("B route provides all required data states and responsive system rules", () => {
  for (const state of ["complete", "partial", "loading", "error", "unknown"])
    assert.match(component, new RegExp(`${state}:`));
  assert.match(css, /\.platformRoute/);
  assert.match(css, /@media\s*\(max-width:\s*1100px\)/);
  assert.match(css, /@media\s*\(max-width:\s*760px\)/);
  assert.match(css, /\.platformSourceTable/);
  assert.match(css, /\.platformExecution/);
});

test("B mobile Director puts the task and action before execution details", () => {
  const director = component.slice(
    component.indexOf("function PlatformDirector"),
    component.indexOf("function PlatformPrototype"),
  );
  const title = director.indexOf("Расход без подтверждённой выручки");
  const limitation = director.indexOf("PlatformDataNotice");
  const amount = director.indexOf("platformObservedAmount");
  const nextStep = director.indexOf("platformNextStep");
  assert.ok(title < limitation && limitation < amount && amount < nextStep);
  assert.ok(director.indexOf("platformFinding") < director.indexOf("platformExecution"));
  assert.match(director, /platformActionControls[\s\S]*STOP/);
  assert.doesNotMatch(css, /\.platformExecution\s*\{[\s\S]*?order:\s*-1/);
});

test("cookie choice keeps an explicit essential-only path", () => {
  assert.match(cookieConsent, /Только обязательные/);
  assert.match(cookieConsent, /save\(\{analytics:false,marketing:false\}\)/);
  assert.match(cookieConsent, /localStorage\.setItem\(STORAGE_KEY/);
  assert.doesNotMatch(cookieConsent, /display:\s*none|remove\(\)/);
});

test("B work screens use readable body and secondary type tokens", () => {
  assert.match(css, /--platform-body:\s*15px/);
  assert.match(css, /--platform-secondary:\s*12px/);
  assert.match(css, /\.platformEvidence li small[\s\S]*font-size:\s*var\(--platform-secondary\)/);
  assert.match(css, /\.platformDataBanner p[\s\S]*font-size:\s*var\(--platform-secondary\)/);
});

test("B decision story exposes unambiguous numbered connections", () => {
  assert.match(component, /data-from=\{item\.key\}/);
  assert.match(component, /data-to=\{decisionStory\[index \+ 1\]\.key\}/);
  assert.match(component, /aria-label=\{`Переход \$\{item\.key\} → \$\{decisionStory\[index \+ 1\]\.key\}`\}/);
});

test("B decision story joins 03 to 04 with an elbow ending at card 04", () => {
  assert.match(
    css,
    /\.step3 > i\s*\{[\s\S]*?width:\s*calc\(54% \+ 23px\)[\s\S]*?height:\s*56px[\s\S]*?border-right:\s*2px solid var\(--study-ink\)[\s\S]*?border-bottom:\s*2px solid var\(--study-ink\)/,
  );
  assert.match(
    css,
    /\.step3 > i::after\s*\{[\s\S]*?left:\s*-1px[\s\S]*?transform:\s*rotate\(-135deg\)/,
  );
  assert.match(
    css,
    /\.step4 > i\s*\{[\s\S]*?left:\s*-31px[\s\S]*?transform:\s*none/,
  );
  assert.match(
    css,
    /\.platformRoute \.orbitStep > i\s*\{[\s\S]*?width:\s*2px[\s\S]*?height:\s*22px[\s\S]*?transform:\s*none/,
  );
});
