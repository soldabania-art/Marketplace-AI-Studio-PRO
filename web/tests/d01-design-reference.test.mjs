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
