import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request) {
  try {
    const body = await request.json()
    const action = body?.action === 'confirm' ? 'confirm' : 'request'
    const path = action === 'confirm'
      ? '/api/v1/auth/password-reset/confirm'
      : '/api/v1/auth/password-reset/request'
    const payloadBody = action === 'confirm'
      ? { token: body.token, new_password: body.new_password }
      : { email: body.email }

    const { response, payload } = await backendRequest(path, {
      method: 'POST',
      body: JSON.stringify(payloadBody),
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || 'Не удалось выполнить операцию восстановления' },
        { status: response.status }
      )
    }

    return NextResponse.json({ ok: true, ...payload }, { status: response.status })
  } catch (error) {
    const message = error?.code === 'BACKEND_NOT_CONFIGURED'
      ? 'Сервер восстановления доступа ещё не подключён.'
      : 'Сервис восстановления доступа временно недоступен.'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
