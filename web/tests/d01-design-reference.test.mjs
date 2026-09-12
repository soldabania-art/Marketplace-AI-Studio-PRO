import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const component = fs.readFileSync(new URL('../components/D01DesignReference.js', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../app/design-reference/d01.css', import.meta.url), 'utf8')

test('D01 stays an isolated synthetic prototype without backend calls', () => {
  assert.match(component, /Синтетические данные/)
  assert.doesNotMatch(component, /fetch\s*\(/)
  assert.match(component, /directionHref\('ledger', 'connect'/)
  assert.match(component, /directionHref\('ledger','director'/)
})

test('D01 exposes both directions and required interface states', () => {
  assert.match(component, /Operational Ledger/)
  assert.match(component, /Signal Room/)
  for (const state of ['complete','partial','loading','error','unknown']) assert.match(component, new RegExp(`'${state}'`))
  assert.match(component, /Сумка-шоппер женская повседневная/)
})

test('D01 includes keyboard focus, mobile and reduced-motion rules', () => {
  assert.match(css, /:focus-visible/)
  assert.match(css, /prefers-reduced-motion:reduce/)
  assert.match(css, /@media\(max-width:760px\)/)
})
