import { createHmac } from 'node:crypto'
import { test, expect } from '@playwright/test'

const password = process.env.E2E_PASSWORD
const secret = process.env.E2E_TOTP_SECRET

if (!password || !secret) {
  throw new Error('E2E_PASSWORD and E2E_TOTP_SECRET are required for isolated browser fixtures')
}
const storeA = 'e2e00000-0000-4000-8000-0000000000a1'
const storeB = 'e2e00000-0000-4000-8000-0000000000b2'

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
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Пароль').fill(password)
  await page.getByRole('button', { name: /Войти/ }).click()
  await page.getByLabel('Код подтверждения').fill(totp())
  await page.getByRole('button', { name: /Подтвердить/ }).click()
  await expect(page).toHaveURL(/\/account/)
}

async function onlyEssential(page) {
  const button = page.getByRole('button', { name: 'Только обязательные' })
  if (await button.isVisible()) await button.click()
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
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('mai_cookie_consent') || '{}'))).toMatchObject({ analytics: false, marketing: false })
  await expect(page.locator('html')).toHaveJSProperty('scrollWidth', await page.evaluate(() => document.documentElement.clientWidth))
  await page.keyboard.press('Tab')
  expect(await page.evaluate(() => document.activeElement?.tagName)).toMatch(/A|BUTTON/)
  if (testInfo.project.name === 'mobile-390') expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath(`d02-${testInfo.project.name}.png`), fullPage: true })
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
  await expect(page.getByRole('alert')).toContainText('STOP активен')
  await page.screenshot({ path: testInfo.outputPath(`d03-mock-${testInfo.project.name}.png`), fullPage: true })
})

test('actual backend: platform roles, MFA/step-up and store scope remain server-enforced', async ({ page }) => {
  await login(page, 'owner.e2e@example.test')
  const missingStepUp = await page.request.patch('/api/admin', { data: { action: 'set_user_status', user_id: 'e2e-viewer', active: false } })
  expect(missingStepUp.status()).toBe(428)
  const stepUp = await page.request.post('/api/auth/step-up', { data: { password, code: totp() } })
  expect(stepUp.status()).toBe(200)
  await page.goto('/admin'); await expect(page.getByText(/Обзор для владельца и команды/)).toBeVisible()
  const stores = await page.request.get('/api/stores'); const list = await stores.json()
  expect(list.stores.map(item => item.id)).toEqual(expect.arrayContaining([storeA, storeB]))
  await page.context().clearCookies(); await login(page, 'viewer.e2e@example.test')
  const viewerAdmin = await page.request.get('/api/admin'); expect(viewerAdmin.status()).toBe(403)
  const viewerMutation = await page.request.patch('/api/director/control', { data: { store_id: storeA, stopped: true, reason: 'E2E' } }); expect(viewerMutation.status()).toBe(403)
  await page.context().clearCookies(); await login(page, 'manager.e2e@example.test')
  const managerOverview = await page.request.get('/api/admin'); expect(managerOverview.status()).toBe(200)
  const managerMutation = await page.request.patch('/api/admin', { data: { action: 'set_user_status', user_id: 'e2e-viewer', active: false } }); expect(managerMutation.status()).toBe(403)
})
