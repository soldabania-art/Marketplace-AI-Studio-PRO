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
  assert.match(component, /Синтетические данные/);
  assert.doesNotMatch(component, /fetch\s*\(/);
  assert.match(component, /directionHref\(["']ledger["'],\s*["']connect["']/);
  assert.match(component, /directionHref\(["']ledger["'],\s*["']director["']/);
});

test("D01 exposes both directions and required interface states", () => {
  assert.match(component, /Operational Ledger/);
  assert.match(component, /Signal Room/);
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
  assert.match(
    css,
    /\.has-prototype\s*>\s*\.referenceBar\s*\{\s*display:\s*none/,
  );
  assert.match(css, /\.inlineControl/);
});

test("D01 demo controls provide local reactions without writes", () => {
  assert.match(component, /setActionStatus\("approved"\)/);
  assert.match(component, /setActionStatus\("rejected"\)/);
  assert.match(component, /Локально, без запросов к WB/);
  assert.match(component, /Без записи в WB/);
});
