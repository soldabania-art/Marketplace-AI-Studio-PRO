import assert from 'node:assert/strict'
import test from 'node:test'

import { createPlatformAdminLoader, projectManagerGrantPayload, queueBarWidth } from '../lib/platformAdmin.mjs'

const response = (payload, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => payload })
const overview = total => ({
  as_of: '2026-09-13T12:00:00Z',
  users: { total, enabled: total, new_7d: 0 },
  operations: { workspaces: 0, active_stores: 0, connections_saved: 0 },
  jobs: {
    queued: 0, running: 0, retry: 0, dead: 0, succeeded_24h: 0,
    backlog: { ready: 0, future_cooldown: 0, oldest_ready_age_seconds: null },
    running_leases: { fresh: 0, stale: 0, missing_timestamp: 0, lease_seconds: 300 },
  },
})

test('project manager requests only safe overview aggregates', async () => {
  const paths = []
  const loader = createPlatformAdminLoader(async path => {
    paths.push(path)
    if (path === '/api/auth/me') return response({ platform_role: 'project_manager' })
    return response(overview(4))
  })
  const data = await loader.load()
  assert.deepEqual(paths, ['/api/auth/me', '/api/admin?resource=overview'])
  assert.equal(data.overview.users.total, 4)
  assert.deepEqual(data.users, [])
  assert.equal(data.jobs, null)
  assert.deepEqual(data.team, [])
})

test('owner overview survives a failed detail request', async () => {
  const loader = createPlatformAdminLoader(async path => {
    if (path === '/api/auth/me') return response({ platform_role: 'owner' })
    if (path === '/api/admin?resource=overview') return response(overview(7))
    if (path === '/api/admin?resource=jobs') return response({ error: 'jobs unavailable' }, 503)
    return response({ items: [] })
  })
  const data = await loader.load()
  assert.equal(data.overview.users.total, 7)
  assert.equal(data.jobs, null)
  assert.match(data.detailErrors.jobs, /jobs unavailable/)
})

test('401 detail response revokes and clears all privileged data', async () => {
  const loader = createPlatformAdminLoader(async path => {
    if (path === '/api/auth/me') return response({ platform_role: 'owner' })
    if (path === '/api/admin?resource=team') return response({ error: 'revoked' }, 401)
    if (path === '/api/admin?resource=overview') return response({ users: { total: 7 } })
    return response({ items: [] })
  })
  await assert.rejects(loader.load(), error => error.status === 401)
})

test('unauthorized role never requests or returns privileged data', async () => {
  const paths = []
  const loader = createPlatformAdminLoader(async path => {
    paths.push(path)
    return response({ platform_role: null })
  })
  await assert.rejects(loader.load(), /Нет доступа/)
  assert.deepEqual(paths, ['/api/auth/me'])
})

test('a late response from an older load cannot replace current role data', async () => {
  let releaseFirst
  let authCall = 0
  const loader = createPlatformAdminLoader(async path => {
    if (path === '/api/auth/me' && authCall++ === 0) return new Promise(resolve => { releaseFirst = () => resolve(response({ platform_role: 'owner' })) })
    if (path === '/api/auth/me') return response({ platform_role: 'project_manager' })
    return response(overview(1))
  })
  const stale = loader.load()
  const current = loader.load()
  releaseFirst()
  assert.equal(await stale, null)
  assert.equal((await current).role, 'project_manager')
})

test('grant payload fixes the only HTTP-grantable role', () => {
  assert.deepEqual(projectManagerGrantPayload('user-1'), { action: 'grant_project_manager', user_id: 'user-1' })
})

test('malformed aggregate response is rejected instead of rendered as zero or NaN', async () => {
  const loader = createPlatformAdminLoader(async path => path === '/api/auth/me'
    ? response({ platform_role: 'project_manager' })
    : response({ as_of: 'not-a-date', users: { total: -1 } }))
  await assert.rejects(loader.load(), /Некорректные данные обзора/)
})

test('queue bars retain the exact count ratio and support an empty queue', () => {
  assert.equal(queueBarWidth(1, 1000), 0.1)
  assert.equal(queueBarWidth(0, 0), 0)
})
