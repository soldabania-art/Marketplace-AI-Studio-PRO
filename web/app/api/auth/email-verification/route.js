import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request) {
  try {
    const body = await request.json()
    const action = body?.action === 'confirm' ? 'confirm' : 'request'
    const path = action === 'confirm'
      ? '/api/v1/auth/email-verification/confirm'
      : '/api/v1/auth/email-verification/request'

    const headers = {}
    if (action === 'request') {
      const cookieStore = await cookies()
      const token = cookieStore.get('mai_session')?.value
      if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
      headers.Authorization = `Bearer ${token}`
    }

    const { response, payload } = await backendRequest(path, {
      method: 'POST',
      headers,
      body: JSON.stringify(action === 'confirm' ? { token: body.token } : {}),
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || 'Не удалось подтвердить email' },
        { status: response.status }
      )
    }

    return NextResponse.json({ ok: true, ...payload }, { status: response.status })
  } catch (error) {
    const message = error?.code === 'BACKEND_NOT_CONFIGURED'
      ? 'Сервер подтверждения email ещё не подключён.'
      : 'Сервис подтверждения email временно недоступен.'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
