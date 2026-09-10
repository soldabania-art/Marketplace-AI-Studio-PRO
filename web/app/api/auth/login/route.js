import { NextResponse } from 'next/server'
import { backendRequest, sessionCookieOptions } from '../../../../lib/backend'

export async function POST(request) {
  try {
    const body = await request.json()
    const { response, payload } = await backendRequest('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || 'Не удалось войти' },
        { status: response.status }
      )
    }

    if (payload.mfa_required) {
      return NextResponse.json({
        ok: false,
        mfa_required: true,
        mfa_challenge_token: payload.mfa_challenge_token,
      })
    }

    if (!payload.access_token) {
      return NextResponse.json({ error: 'Сервер не выдал безопасную сессию' }, { status: 502 })
    }

    const result = NextResponse.json({ ok: true })
    result.cookies.set('mai_session', payload.access_token, sessionCookieOptions())
    return result
  } catch (error) {
    const message = error?.code === 'BACKEND_NOT_CONFIGURED'
      ? 'Сервер авторизации ещё не подключён.'
      : 'Сервис авторизации временно недоступен.'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
