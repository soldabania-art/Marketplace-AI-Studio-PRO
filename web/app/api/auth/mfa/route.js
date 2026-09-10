import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest, sessionCookieOptions } from '../../../../lib/backend'

async function sessionToken() {
  const store = await cookies()
  return store.get('mai_session')?.value
}

function unavailable(error) {
  const message = error?.code === 'BACKEND_NOT_CONFIGURED'
    ? 'Backend API ещё не подключён.'
    : 'Сервис дополнительной защиты временно недоступен.'
  return NextResponse.json({ error: message }, { status: 503 })
}

export async function GET() {
  const token = await sessionToken()
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  try {
    const { response, payload } = await backendRequest('/api/v1/auth/mfa/status', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) return NextResponse.json({ error: payload?.detail || 'Не удалось проверить MFA' }, { status: response.status })
    return NextResponse.json(payload)
  } catch (error) { return unavailable(error) }
}

export async function POST(request) {
  try {
    const body = await request.json()
    const action = body.action
    const paths = {
      login: '/api/v1/auth/mfa/login',
      setup: '/api/v1/auth/mfa/setup',
      confirm: '/api/v1/auth/mfa/confirm',
      disable: '/api/v1/auth/mfa/disable',
    }
    if (!paths[action]) return NextResponse.json({ error: 'Неизвестное действие MFA' }, { status: 400 })
    const token = action === 'login' ? null : await sessionToken()
    if (action !== 'login' && !token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
    const { action: _action, ...payloadBody } = body
    const { response, payload } = await backendRequest(paths[action], {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: JSON.stringify(payloadBody),
    })
    if (!response.ok) return NextResponse.json({ error: payload?.detail || 'Операция MFA не выполнена' }, { status: response.status })
    if (action === 'login') {
      if (!payload.access_token) return NextResponse.json({ error: 'Сервер не выдал безопасную сессию' }, { status: 502 })
      const result = NextResponse.json({ ok: true })
      result.cookies.set('mai_session', payload.access_token, sessionCookieOptions())
      return result
    }
    return NextResponse.json(payload)
  } catch (error) { return unavailable(error) }
}
