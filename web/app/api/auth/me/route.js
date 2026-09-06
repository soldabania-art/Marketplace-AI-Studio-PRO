import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET() {
  const cookieStore = await cookies()
  const token = cookieStore.get('mai_session')?.value
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })

  try {
    const { response, payload } = await backendRequest('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) {
      const result = NextResponse.json({ error: payload?.detail || 'Сессия недействительна' }, { status: response.status })
      if (response.status === 401) result.cookies.set('mai_session', '', { path: '/', maxAge: 0 })
      return result
    }
    return NextResponse.json(payload)
  } catch (error) {
    const message = error?.code === 'BACKEND_NOT_CONFIGURED'
      ? 'Backend API ещё не подключён.'
      : 'Сервис аккаунта временно недоступен.'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
