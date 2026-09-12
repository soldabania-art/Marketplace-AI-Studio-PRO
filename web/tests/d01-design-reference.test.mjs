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
  assert.match(component, /routeHref\(["']connect["']/);
  assert.match(component, /routeHref\(["']director["']/);
  assert.doesNotMatch(component, /direction=/);
});

test("D01 exposes one final TROVENDI direction and required interface states", () => {
  assert.doesNotMatch(component, /Signal Room|DirectionSwitcher|SignalGraphic/);
  assert.match(component, /traceStory/);
  assert.match(component, /traceMobile/);
  assert.match(component, /КОНТУР РЕШЕНИЯ/);
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
  assert.match(css, /@media\s*\(max-width:\s*760px\)/);
  assert.match(css, /\.traceMobile/);
  assert.match(css, /\.prototypeHeader/);
  assert.match(css, /\.inlineControl/);
});

test("D01 fixes the approved cloud ink blue and cyan tokens", () => {
  for (const token of [
    "--paper: #f6f8fc",
    "--panel: #ffffff",
    "--ink: #111827",
    "--blue: #345cff",
    "--cyan: #71d7f7",
    "--emerald: #11845b",
  ]) {
    assert.match(css, new RegExp(token));
  }
});

test("D01 demo controls provide local reactions without writes", () => {
  assert.match(component, /setActionStatus\("approved"\)/);
  assert.match(component, /setActionStatus\("rejected"\)/);
  assert.match(component, /Локально, без запросов к WB/);
  assert.match(component, /Без записи в WB/);
});
