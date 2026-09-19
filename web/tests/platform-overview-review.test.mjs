import assert from 'node:assert/strict'
import test from 'node:test'
import { createPlatformAdminLoader, queueBarWidth } from '../lib/platformAdmin.mjs'

function overview() {
  return {
    as_of: '2026-09-13T12:00:00+00:00',
    users: { total: 0, enabled: 0, new_7d: 0 },
    operations: { workspaces: 0, active_stores: 0, connections_saved: 0 },
    jobs: {
      queued: 0, running: 0, retry: 0, dead: 0, succeeded_24h: 0,
      backlog: { ready: 0, future_cooldown: 0, oldest_ready_age_seconds: null },
      running_leases: { fresh: 0, stale: 0, missing_timestamp: 0, lease_seconds: 300 },
    },
    availability: { confirmed_revenue: null, mrr: null, ai_actual_cost: null, task_assignments: null },
  }
}

const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
const managerLoader = value => createPlatformAdminLoader(async path => response(path === '/api/auth/me' ? { platform_role: 'project_manager' } : value))

for (const value of [0, 1, '1', undefined, 'not-a-date']) {
  test(`overview rejects malformed timestamp ${String(value)}`, async () => {
    const data = overview()
    data.as_of = value
    await assert.rejects(managerLoader(data).load())
  })
}

for (const value of [null, undefined, -1, 0.5, '0', Infinity, NaN, Number.MAX_SAFE_INTEGER + 1]) {
  test(`overview rejects malformed count ${String(value)}`, async () => {
    const data = overview()
    data.jobs.dead = value
    await assert.rejects(managerLoader(data).load())
  })
}

test('an observed zero and unavailable revenue remain different', async () => {
  const data = await managerLoader(overview()).load()
  assert.equal(data.overview.jobs.dead, 0)
  assert.equal(data.overview.availability.confirmed_revenue, null)
  assert.equal(data.overview.jobs.backlog.oldest_ready_age_seconds, null)
})

test('a small queue value is not visually exaggerated', () => {
  assert.equal(queueBarWidth(1, 1000), 0.1)
  assert.equal(queueBarWidth(1000, 1000), 100)
  assert.equal(queueBarWidth(0, 1000), 0)
  assert.equal(queueBarWidth(0, 0), 0)
})

test('owner detail failure preserves overview and identifies the unavailable source', async () => {
  const loader = createPlatformAdminLoader(async path => {
    if (path === '/api/auth/me') return response({ platform_role: 'owner' })
    if (path.endsWith('overview')) return response(overview())
    if (path.endsWith('users')) return response({ error: 'Users unavailable' }, 503)
    return response({ items: [] })
  })
  const data = await loader.load()
  assert.equal(data.overview.users.total, 0)
  assert.equal(data.detailErrors.users, 'Users unavailable')
})

test('revoked access in an owner detail discards the complete response', async () => {
  const loader = createPlatformAdminLoader(async path => {
    if (path === '/api/auth/me') return response({ platform_role: 'owner' })
    if (path.endsWith('overview')) return response(overview())
    if (path.endsWith('team')) return response({ error: 'Access revoked' }, 403)
    return response({ items: [] })
  })
  await assert.rejects(loader.load(), error => error.status === 403)
})
