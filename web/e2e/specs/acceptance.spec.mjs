import { createHmac } from 'node:crypto'
import { mkdir } from 'node:fs/promises'
import { test, expect } from '@playwright/test'

const password = process.env.E2E_PASSWORD
const secret = process.env.E2E_TOTP_SECRET

if (!password || !secret) {
  throw new Error('E2E_PASSWORD and E2E_TOTP_SECRET are required for isolated browser fixtures')
}
const storeA = 'e2e00000-0000-4000-8000-0000000000a1'
const storeB = 'e2e00000-0000-4000-8000-0000000000b2'
const browserErrors = new WeakMap()

test.beforeEach(async ({ page }) => {
  const errors = []
  browserErrors.set(page, errors)
  page.on('pageerror', error => errors.push(`pageerror: ${error.message}`))
  page.on('console', message => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
})

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) || []).toEqual([])
})

function totp() {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const char of secret) bits += alphabet.indexOf(char).toString(2).padStart(5, '0')
  const bytes = Buffer.from(bits.match(/.{8}/g).map(value => Number.parseInt(value, 2)))
  const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000)))
  const digest = createHmac('sha1', bytes).update(counter).digest(); const offset = digest[19] & 15
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, '0')
}

async function login(page, email) {
  await page.goto('/login')
  await onlyEssential(page)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Пароль').fill(password)
  const loginResponse = page.waitForResponse(response =>
    response.request().method() === 'POST' && response.url().endsWith('/api/auth/login'),
  )
  await page.getByRole('button', { name: /Войти/ }).click()
  expect((await loginResponse).status()).toBe(200)
  await expect(page.getByLabel('Код подтверждения')).toBeVisible()
  await page.getByLabel('Код подтверждения').fill(totp())
  const mfaResponse = page.waitForResponse(response =>
    response.request().method() === 'POST' && response.url().endsWith('/api/auth/mfa'),
  )
  await page.getByRole('button', { name: /Подтвердить/ }).click()
  expect((await mfaResponse).status()).toBe(200)
  await expect(page).toHaveURL(/\/account/)
}

async function onlyEssential(page) {
  await expect(page.locator('html')).toHaveAttribute('data-trovendi-ready', 'true', { timeout: 15_000 })
  const hasConsent = await page.evaluate(() => localStorage.getItem('mai_cookie_consent_v1') !== null)
  if (hasConsent) return
  const button = page.getByRole('button', { name: 'Только обязательные' })
  await expect(button).toBeVisible()
  await expect(button).toBeEnabled()
  await button.click()
  await expect(button).toBeHidden()
}

async function evidencePath(name) {
  await mkdir('e2e-artifacts/screenshots', { recursive: true })
  return `e2e-artifacts/screenshots/${name}`
}

async function browserApi(page, url, { method = 'GET', data } = {}) {
  return page.evaluate(async ({ url, method, data }) => {
    const response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: data === undefined ? undefined : JSON.stringify(data),
    })
    let payload = null
    try { payload = await response.json() } catch {}
    return { status: response.status, payload }
  }, { url, method, data })
}

test('D02 preserves a selected planned integration and essential-only consent', async ({ page }, testInfo) => {
  await page.goto('/#bundle'); await onlyEssential(page)
  await page.getByRole('button', { name: /Ozon.*Запланировано/ }).click()
  await page.getByRole('button', { name: '1 магазин' }).click()
  await page.getByRole('button', { name: /AI Director/ }).click()
  const bundle = page.getByText('ЗАПРОШЕННЫЙ МАРШРУТ').locator('..')
  await expect(bundle).toContainText('интерес к запланированной интеграции')
  await expect(bundle).toContainText('Доступ')
  await page.getByRole('link', { name: 'Перейти к регистрации' }).click()
  await expect(page.getByText('PRO указан как желаемый план')).toBeVisible()
  await expect(page.getByText(/интерес к запланированной интеграции: Ozon/)).toBeVisible()
  await page.getByRole('link', { name: /Вернуться к выбранному набору/ }).click()
  await expect(bundle).toContainText('Ozon')
  await expect(bundle).toContainText('до 1 магазинов')
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('mai_cookie_consent_v1') || '{}'))).toMatchObject({ analytics: false, marketing: false })
  await expect(page.locator('html')).toHaveJSProperty('scrollWidth', await page.evaluate(() => document.documentElement.clientWidth))
  await page.keyboard.press('Tab')
  expect(await page.evaluate(() => document.activeElement?.tagName)).toMatch(/A|BUTTON/)
  if (testInfo.project.name === 'mobile-390') expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true)
  await page.screenshot({ path: await evidencePath(`d02-${testInfo.project.name}.png`), fullPage: true })
})

test('D03 renders mock-controlled states without impersonating server authorization', async ({ page }, testInfo) => {
  const states = ['missing', 'stale', 'incomplete', 'error']
  let state = 'missing'
  const payload = () => ({ store_id: storeA, store_name: 'Store A — deliberately long visible acceptance name', mode: 'partial', generated_at: new Date().toISOString(), sources: states.map(name => ({ name, state: name === state ? state : 'live', last_snapshot_at: null })), actions: [], tracked_actions: [], audit: [], control: { stopped: true, reason: 'E2E STOP' }, automation: { note: 'E2E' }, ranking: { formula: 'E2E' }, summary: { what_happened: 'E2E', money_losses: { observed_kopecks: null }, today_actions: 0, safe_actions: 0, approval_required: 0, measured_changes: 'E2E' } })
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [{ id: storeA, name: 'Store A — deliberately long visible acceptance name', workspace_id: 'w' }, { id: storeB, name: 'Store B — deliberately long visible acceptance name', workspace_id: 'w' }], workspaces: [{ id: 'w', role: 'analyst', can_manage_stores: false }] } }))
  await page.route('**/api/director?*', route => route.fulfill({ json: payload() }))
  await page.addInitScript(id => localStorage.setItem('mai_store_id', id), storeA)
  await page.goto('/director'); await onlyEssential(page)
  for (const item of states) { state = item; await page.reload(); await expect(page.getByText(/Очередь ограничена состоянием источников/)).toBeVisible() }
  await expect(page.getByText('Доступен только просмотр')).toBeVisible()
  await expect(page.getByRole('alert').filter({ hasText: 'STOP активен' })).toContainText('STOP активен')
  await page.screenshot({ path: await evidencePath(`d03-mock-${testInfo.project.name}.png`), fullPage: true })
})

test('actual backend: platform roles, MFA/step-up and store scope remain server-enforced', async ({ page }, testInfo) => {
  const suffix = testInfo.project.name.replaceAll('-', '.')
  const viewerId = `e2e-viewer-${testInfo.project.name}`
  await login(page, `owner.${suffix}.e2e@example.com`)
  const missingStepUp = await browserApi(page, '/api/admin', { method: 'PATCH', data: { action: 'set_user_status', user_id: viewerId, active: false } })
  expect(missingStepUp.status).toBe(428)
  const stepUp = await browserApi(page, '/api/auth/step-up', { method: 'POST', data: { password, code: totp() } })
  expect(stepUp.status).toBe(200)
  await page.goto('/admin'); await expect(page.getByText(/Обзор для владельца и команды/)).toBeVisible()
  const stores = await browserApi(page, '/api/stores')
  expect(stores.payload.stores.map(item => item.id)).toEqual(expect.arrayContaining([storeA, storeB]))
  await page.context().clearCookies(); await login(page, `viewer.${suffix}.e2e@example.com`)
  const viewerAdmin = await browserApi(page, '/api/admin'); expect(viewerAdmin.status).toBe(403)
  const viewerMutation = await browserApi(page, '/api/director/control', { method: 'PATCH', data: { store_id: storeA, stopped: true, reason: 'E2E' } }); expect(viewerMutation.status).toBe(403)
  await page.context().clearCookies(); await login(page, `manager.${suffix}.e2e@example.com`)
  const managerOverview = await browserApi(page, '/api/admin'); expect(managerOverview.status).toBe(200)
  const managerMutation = await browserApi(page, '/api/admin', { method: 'PATCH', data: { action: 'set_user_status', user_id: viewerId, active: false } }); expect(managerMutation.status).toBe(403)
})
