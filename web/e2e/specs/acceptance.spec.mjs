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
const foreignStore = 'e2e00000-0000-4000-8000-0000000000f0'
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
  const code = totp()
  await page.getByLabel('Код подтверждения').fill(code)
  const mfaResponse = page.waitForResponse(response =>
    response.request().method() === 'POST' && response.url().endsWith('/api/auth/mfa'),
  )
  await page.getByRole('button', { name: /Подтвердить/ }).click()
  expect((await mfaResponse).status()).toBe(200)
  await expect(page).toHaveURL(/\/account/)
  return code
}

async function consumeExpectedHttpError(page, status) {
  const marker = `status of ${status}`
  await expect.poll(() => (browserErrors.get(page) || []).some(message => message.includes(marker))).toBe(true)
  const errors = browserErrors.get(page) || []
  errors.splice(errors.findIndex(message => message.includes(marker)), 1)
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

test('T16 labels planned module screens before users can invoke unavailable actions', async ({ page }) => {
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [{ id: storeA, name: 'Store A', workspace_id: 'w' }], workspaces: [{ id: 'w', role: 'owner', can_manage_stores: true }] } }))
  await page.addInitScript(id => localStorage.setItem('mai_store_id', id), storeA)
  const screens = [
    ['/seo', 'Экран планируется', 'Открыть AI Card Factory', '/card-factory', 'Запустить SEO-аудит'],
    ['/ads', 'Экран планируется', 'Открыть Profit Center', '/profit', 'Проверить рекламу'],
    ['/inventory', 'Частично доступно', 'Найти склады FBO / FBW', '/fbo-slots', 'Проверить остатки'],
    ['/reports', 'Экран планируется', 'Открыть Profit Center', '/profit', 'Сформировать отчёт'],
    ['/autopilot', 'Экран планируется', 'Открыть AI Director', '/director', 'Настроить автопилот'],
  ]
  for (const [href, stage, linkName, linkHref, unavailableAction] of screens) {
    await page.goto(href); await onlyEssential(page)
    await expect(page.getByText('СТАТУС ЭКРАНА')).toBeVisible()
    await expect(page.getByText(stage, { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: linkName })).toHaveAttribute('href', linkHref)
    await expect(page.getByRole('button', { name: unavailableAction })).toHaveCount(0)
  }
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

test('D03 exposes loading, backend error and no-store as separate visible states', async ({ page }) => {
  let release
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [{ id: storeA, name: 'Store A', workspace_id: 'w' }], workspaces: [{ id: 'w', role: 'analyst', can_manage_stores: false }] } }))
  await page.route('**/api/director?*', route => new Promise(resolve => { release = () => route.fulfill({ status: 503, json: { error: 'E2E source failure' } }).then(resolve) }))
  await page.addInitScript(id => localStorage.setItem('mai_store_id', id), storeA)
  await page.goto('/director'); await onlyEssential(page)
  await expect(page.getByText('Проверяем факты выбранного магазина')).toBeVisible()
  const directorFailure = page.waitForResponse(response => response.url().includes('/api/director?') && response.status() === 503)
  await release(); await directorFailure; await expect(page.locator('.directorBError')).toContainText('Director не загрузил очередь')
  await consumeExpectedHttpError(page, 503)
  await page.unroute('**/api/stores')
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [], workspaces: [] } }))
  await page.reload(); await expect(page.locator('.directorBState h2', { hasText: 'Магазин не выбран' })).toBeVisible()
})

test('D03 visibly fences a delayed A response across A → B → A and honors reduced motion', async ({ page }, testInfo) => {
  let aRequests = 0
  let releaseOldA
  let releaseReducedMotionRefresh
  let oldAStarted
  const oldAStartedPromise = new Promise(resolve => { oldAStarted = resolve })
  const payload = (id, marker) => ({ store_id: id, store_name: `Store ${id === storeA ? 'A' : 'B'}`, mode: 'partial', generated_at: new Date().toISOString(), sources: [{ name: 'catalog', state: 'live' }, { name: 'stocks', state: 'live' }, { name: 'sales_velocity_7d', state: 'live' }], actions: [], tracked_actions: [], audit: [], control: { stopped: false }, automation: { note: 'E2E automation' }, ranking: { formula: 'E2E ranking' }, summary: { what_happened: `${marker} summary`, money_losses: { observed_kopecks: null }, today_actions: 0, safe_actions: 0, approval_required: 0, measured_changes: 'E2E unchanged' } })
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [{ id: storeA, name: 'Store A', workspace_id: 'w' }, { id: storeB, name: 'Store B', workspace_id: 'w' }], workspaces: [{ id: 'w', role: 'owner', can_manage_stores: true }] } }))
  await page.route('**/api/director?*', route => {
    const id = new URL(route.request().url()).searchParams.get('store_id')
    if (id === storeA && ++aRequests === 2) {
      oldAStarted()
      return new Promise(resolve => { releaseOldA = () => route.fulfill({ json: payload(storeA, 'OLD A') }).then(resolve) })
    }
    if (id === storeA && aRequests === 4) return new Promise(resolve => { releaseReducedMotionRefresh = () => route.fulfill({ json: payload(storeA, 'CURRENT A') }).then(resolve) })
    return route.fulfill({ json: payload(id, id === storeA ? 'CURRENT A' : 'CURRENT B') })
  })
  await page.addInitScript(id => localStorage.setItem('mai_store_id', id), storeA)
  await page.goto('/director'); await onlyEssential(page)
  await expect(page.getByText('CURRENT A summary', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Обновить факты' }).click(); await oldAStartedPromise
  await page.evaluate(({ event, id }) => window.dispatchEvent(new CustomEvent(event, { detail: { store_id: id } })), { event: 'mai:store-changed', id: storeB })
  await expect(page.getByText('CURRENT B summary', { exact: true })).toBeVisible()
  await page.evaluate(({ event, id }) => window.dispatchEvent(new CustomEvent(event, { detail: { store_id: id } })), { event: 'mai:store-changed', id: storeA })
  await expect(page.getByText('CURRENT A summary', { exact: true })).toBeVisible()
  await releaseOldA()
  await expect(page.getByText('OLD A')).toHaveCount(0)
  await page.keyboard.press('Tab')
  await expect(page.locator(':focus-visible')).toHaveCount(1)
  if (testInfo.project.name === 'mobile-390') {
    await page.getByRole('button', { name: 'Обновить факты' }).click()
    const spin = page.locator('.directorBSpin')
    await expect(spin).toBeVisible()
    expect(await spin.evaluate(element => getComputedStyle(element).animationName)).toBe('none')
    await releaseReducedMotionRefresh()
  }
})

test('D03 ignores a delayed A decision response after A → B → A', async ({ page }) => {
  let releaseOldDecision
  let decisionStarted
  const oldDecisionStarted = new Promise(resolve => { decisionStarted = resolve })
  const payload = (id, marker) => ({
    store_id: id, store_name: `Store ${id === storeA ? 'A' : 'B'} — ${marker}`, mode: 'live', generated_at: new Date().toISOString(),
    sources: [{ name: 'catalog', state: 'live' }],
    actions: id === storeA ? [{ id: 'acceptance-action-a', kind: 'check', provider: { label: 'E2E' }, title: 'E2E action', reason: 'E2E reason', evidence: 'E2E evidence', observed_effect_kopecks: null, priority_reason: 'E2E priority', priority_score: 1, urgency: 'low', href: '/account', status: 'proposed', requires_approval: true, can_execute: false, execution_type: null }] : [],
    tracked_actions: [], audit: [], control: { stopped: false }, automation: { note: 'E2E automation' }, ranking: { formula: 'E2E ranking' }, summary: { what_happened: `${marker} summary`, money_losses: { observed_kopecks: null }, today_actions: 0, safe_actions: 0, approval_required: 0, measured_changes: 'E2E unchanged' },
  })
  await page.route('**/api/stores', route => route.fulfill({ json: { stores: [{ id: storeA, name: 'Store A', workspace_id: 'w' }, { id: storeB, name: 'Store B', workspace_id: 'w' }], workspaces: [{ id: 'w', role: 'owner', can_manage_stores: true }] } }))
  await page.route('**/api/director?*', route => {
    const id = new URL(route.request().url()).searchParams.get('store_id')
    return route.fulfill({ json: payload(id, id === storeA ? 'CURRENT A' : 'CURRENT B') })
  })
  await page.route('**/api/director/actions/acceptance-action-a', route => {
    decisionStarted()
    return new Promise(resolve => { releaseOldDecision = () => route.fulfill({ json: { message: 'OLD A decision' } }).then(resolve) })
  })
  await page.addInitScript(id => localStorage.setItem('mai_store_id', id), storeA)
  await page.goto('/director'); await onlyEssential(page)
  const oldDecisionResponse = page.waitForResponse(response => response.url().includes('/api/director/actions/acceptance-action-a') && response.request().method() === 'PATCH')
  await page.getByRole('button', { name: 'Принять в работу' }).click(); await oldDecisionStarted
  await page.evaluate(({ event, id }) => window.dispatchEvent(new CustomEvent(event, { detail: { store_id: id } })), { event: 'mai:store-changed', id: storeB })
  await expect(page.getByText('CURRENT B summary', { exact: true })).toBeVisible()
  await page.evaluate(({ event, id }) => window.dispatchEvent(new CustomEvent(event, { detail: { store_id: id } })), { event: 'mai:store-changed', id: storeA })
  await expect(page.getByText('CURRENT A summary', { exact: true })).toBeVisible()
  await releaseOldDecision(); await oldDecisionResponse
  await page.evaluate(() => new Promise(requestAnimationFrame))
  await expect(page.getByText('OLD A decision', { exact: true })).toHaveCount(0)
  await expect(page.getByText('CURRENT A summary', { exact: true })).toBeVisible()
})
test('account ignores a delayed WB check after the selected store changes', async ({ page }, testInfo) => {
  let releaseCheck
  let checkStarted
  const started = new Promise(resolve => { checkStarted = resolve })
  await login(page, `owner.wb.${testInfo.project.name.replaceAll('-', '.')}.e2e@example.com`)
  await page.route('**/api/marketplace/wildberries?store_id=*', route => route.fulfill({ json: { connected: true, token_saved: true, sources_verified: false, verification: { summary: 'unchecked', sources: [] }, store_id: new URL(route.request().url()).searchParams.get('store_id') } }))
  await page.route(`**/api/marketplace/wildberries/check?store_id=${storeA}`, route => {
    checkStarted()
    return new Promise(resolve => { releaseCheck = () => route.fulfill({ json: { connected: true, token_saved: true, sources_verified: true, verification: { summary: 'complete', sources: [] }, store_id: storeA } }).then(resolve) })
  })
  await page.goto('/account'); await onlyEssential(page); await consumeExpectedHttpError(page, 402)
  const storeSelect = page.locator('select').first()
  await storeSelect.selectOption(storeA)
  await page.getByRole('button', { name: 'Проверить источники' }).click(); await started
  await storeSelect.selectOption(storeB); await expect(page.getByText(/Рабочий магазин:.*Store B/)).toBeVisible()
  await storeSelect.selectOption(storeA); await releaseCheck()
  await expect(page.getByText('Источники ещё не проверены', { exact: true })).toBeVisible()
})

test('actual backend: platform roles, MFA/step-up and store scope remain server-enforced', async ({ page }, testInfo) => {
  test.setTimeout(90_000)
  const suffix = testInfo.project.name.replaceAll('-', '.')
  const viewerId = `e2e-viewer-${testInfo.project.name}`
  const loginCode = await login(page, `owner.${suffix}.e2e@example.com`)
  await consumeExpectedHttpError(page, 402)
  const missingStepUp = await browserApi(page, '/api/admin', { method: 'PATCH', data: { action: 'set_user_status', user_id: viewerId, active: false } })
  expect(missingStepUp.status).toBe(428)
  await consumeExpectedHttpError(page, 428)
  await expect.poll(() => totp(), { timeout: 35_000 }).not.toBe(loginCode)
  const stepUp = await browserApi(page, '/api/auth/step-up', { method: 'POST', data: { password, code: totp() } })
  expect(stepUp.status).toBe(200)
  await page.goto('/admin'); await expect(page.getByText(/Обзор для владельца и команды/)).toBeVisible()
  const stores = await browserApi(page, '/api/stores')
  expect(stores.payload.stores.map(item => item.id)).toEqual(expect.arrayContaining([storeA, storeB]))
  const foreignWb = await browserApi(page, `/api/marketplace/wildberries?store_id=${foreignStore}`)
  expect(foreignWb.status).toBe(404); await consumeExpectedHttpError(page, 404)
  await page.context().clearCookies(); await login(page, `viewer.${suffix}.e2e@example.com`); await consumeExpectedHttpError(page, 402)
  const viewerAdmin = await browserApi(page, '/api/admin'); expect(viewerAdmin.status).toBe(403); await consumeExpectedHttpError(page, 403)
  const viewerMutation = await browserApi(page, '/api/director/control', { method: 'PATCH', data: { store_id: storeA, stopped: true, reason: 'E2E' } }); expect(viewerMutation.status).toBe(403); await consumeExpectedHttpError(page, 403)
  await page.context().clearCookies(); await login(page, `manager.${suffix}.e2e@example.com`); await consumeExpectedHttpError(page, 402)
  const managerOverview = await browserApi(page, '/api/admin'); expect(managerOverview.status).toBe(200)
  const managerMutation = await browserApi(page, '/api/admin', { method: 'PATCH', data: { action: 'set_user_status', user_id: viewerId, active: false } }); expect(managerMutation.status).toBe(403); await consumeExpectedHttpError(page, 403)
})
