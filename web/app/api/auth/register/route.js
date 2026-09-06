import { NextResponse } from 'next/server'
import { backendRequest, sessionCookieOptions } from '../../../../lib/backend'

export async function POST(request) {
  try {
    const body = await request.json()
    const { response, payload } = await backendRequest('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || 'Не удалось создать аккаунт' },
        { status: response.status }
      )
    }

    const result = NextResponse.json({ ok: true }, { status: 201 })
    result.cookies.set('mai_session', payload.access_token, sessionCookieOptions())
    return result
  } catch (error) {
    const message = error?.code === 'BACKEND_NOT_CONFIGURED'
      ? 'Сервер регистрации ещё не подключён.'
      : 'Сервис регистрации временно недоступен.'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
