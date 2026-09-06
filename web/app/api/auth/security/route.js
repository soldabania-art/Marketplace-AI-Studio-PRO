import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function token() {
  const store = await cookies()
  return store.get('mai_session')?.value
}

function failure(error) {
  const message = error?.code === 'BACKEND_NOT_CONFIGURED' ? 'Backend API ещё не подключён.' : 'Сервис безопасности временно недоступен.'
  return NextResponse.json({ error: message }, { status: 503 })
}

export async function GET() {
  const accessToken = await token()
  if (!accessToken) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  try {
    const [sessionsResult, eventsResult] = await Promise.all([
      backendRequest('/api/v1/auth/sessions', { headers: { Authorization: `Bearer ${accessToken}` } }),
      backendRequest('/api/v1/auth/security-events', { headers: { Authorization: `Bearer ${accessToken}` } }),
    ])
    if (!sessionsResult.response.ok) return NextResponse.json({ error: sessionsResult.payload?.detail || 'Не удалось загрузить сессии' }, { status: sessionsResult.response.status })
    if (!eventsResult.response.ok) return NextResponse.json({ error: eventsResult.payload?.detail || 'Не удалось загрузить журнал' }, { status: eventsResult.response.status })
    return NextResponse.json({ sessions: sessionsResult.payload.sessions || [], events: eventsResult.payload.events || [] })
  } catch (error) { return failure(error) }
}

export async function DELETE(request) {
  const accessToken = await token()
  if (!accessToken) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  const { session_id: sessionId } = await request.json()
  if (!sessionId) return NextResponse.json({ error: 'Не указана сессия' }, { status: 400 })
  try {
    const { response, payload } = await backendRequest(`/api/v1/auth/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!response.ok) return NextResponse.json({ error: payload?.detail || 'Не удалось завершить сессию' }, { status: response.status })
    return NextResponse.json(payload)
  } catch (error) { return failure(error) }
}
