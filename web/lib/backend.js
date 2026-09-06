const DEFAULT_TIMEOUT_MS = 10000

export function backendBaseUrl() {
  return (process.env.MARKETPLACE_API_URL || '').replace(/\/$/, '')
}

export async function backendRequest(path, options = {}) {
  const base = backendBaseUrl()
  if (!base) {
    const error = new Error('Backend API is not configured')
    error.code = 'BACKEND_NOT_CONFIGURED'
    throw error
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS)

  try {
    const response = await fetch(`${base}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: controller.signal,
      cache: 'no-store',
    })

    let payload = null
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) payload = await response.json()

    return { response, payload }
  } finally {
    clearTimeout(timeout)
  }
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 12,
  }
}
