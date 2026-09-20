import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const component = fs.readFileSync(new URL('../components/ProfitCenterWorkspace.js', import.meta.url), 'utf8')

test('Profit Center requests a bounded product page and exposes navigation', () => {
  assert.match(component, /page=\$\{productPage\}&page_size=50/)
  assert.match(component, /data\.pagination\?\.total_pages>1/)
  assert.match(component, /setProductPage\(page=>Math\.max\(1,page-1\)\)/)
  assert.match(component, /disabled=\{busy\|\|!data\.pagination\.has_next\}/)
})

test('changing the period returns product pagination to the first page', () => {
  assert.match(component, /setProductPage\(1\);setPeriodDays\(event\.target\.value\)/)
})
