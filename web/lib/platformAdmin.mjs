async function responsePayload(response) {
  const payload = await response.json()
  if (!response.ok) throw Object.assign(new Error(payload?.error || 'Нет доступа к панели управления'), { status: response.status })
  return payload
}

const OVERVIEW_COUNT_PATHS = [
  ['users', 'total'], ['users', 'enabled'], ['users', 'new_7d'],
  ['operations', 'workspaces'], ['operations', 'active_stores'], ['operations', 'connections_saved'],
  ['jobs', 'queued'], ['jobs', 'running'], ['jobs', 'retry'], ['jobs', 'dead'], ['jobs', 'succeeded_24h'],
  ['jobs', 'backlog', 'ready'], ['jobs', 'backlog', 'future_cooldown'],
  ['jobs', 'running_leases', 'fresh'], ['jobs', 'running_leases', 'stale'], ['jobs', 'running_leases', 'missing_timestamp'], ['jobs', 'running_leases', 'lease_seconds'],
]

function validateOverview(value) {
  const validCount = count => Number.isSafeInteger(count) && count >= 0
  const atPath = path => path.reduce((current, key) => current?.[key], value)
  const oldestAge = atPath(['jobs', 'backlog', 'oldest_ready_age_seconds'])
  const utcDateTime = typeof value?.as_of === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value.as_of)
  if (!value || !utcDateTime || Number.isNaN(Date.parse(value.as_of)) || OVERVIEW_COUNT_PATHS.some(path => !validCount(atPath(path))) || (oldestAge !== null && !validCount(oldestAge))) {
    throw new Error('Некорректные данные обзора платформы')
  }
  return value
}

export function queueBarWidth(value, maximum) {
  return maximum > 0 ? (value / maximum) * 100 : 0
}

async function requestAdminData(fetcher, signal) {
  const auth = await responsePayload(await fetcher('/api/auth/me', { cache: 'no-store', signal }))
  const role = auth.platform_role
  if (!['owner', 'project_manager'].includes(role)) throw Object.assign(new Error('Нет доступа к панели управления'), { status: 403 })
  const resources = role === 'owner' ? ['overview', 'users', 'jobs', 'team'] : ['overview']
  const results = await Promise.allSettled(resources.map(async resource => ({
    resource,
    payload: await responsePayload(await fetcher(`/api/admin?resource=${resource}`, { cache: 'no-store', signal })),
  })))
  for (const result of results) {
    if (result.status === 'rejected' && [401, 403].includes(result.reason?.status)) throw result.reason
  }
  if (results[0].status === 'rejected') throw results[0].reason
  const values = Object.fromEntries(results.filter(result => result.status === 'fulfilled').map(result => [result.value.resource, result.value.payload]))
  const detailErrors = Object.fromEntries(results.slice(1).flatMap((result, index) => result.status === 'rejected'
    ? [[resources[index + 1], result.reason?.message || 'Раздел временно недоступен']]
    : []))
  return {
    role,
    overview: validateOverview(values.overview),
    users: role === 'owner' ? values.users?.items || [] : [],
    jobs: role === 'owner' ? values.jobs || null : null,
    team: role === 'owner' ? values.team?.items || [] : [],
    detailErrors,
  }
}

export function createPlatformAdminLoader(fetcher) {
  let sequence = 0
  let controller = null
  return {
    async load() {
      const current = ++sequence
      controller?.abort()
      controller = new AbortController()
      try {
        const data = await requestAdminData(fetcher, controller.signal)
        return current === sequence ? data : null
      } catch (error) {
        if (current !== sequence || error?.name === 'AbortError') return null
        throw error
      }
    },
    cancel() {
      sequence += 1
      controller?.abort()
    },
  }
}

export function projectManagerGrantPayload(userId) {
  return { action: 'grant_project_manager', user_id: userId }
}
