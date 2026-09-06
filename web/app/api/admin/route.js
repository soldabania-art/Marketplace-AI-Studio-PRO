import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

async function adminToken() {
  const cookieStore = await cookies()
  return cookieStore.get('mai_session')?.value
}

export async function GET(request) {
  const token = await adminToken()
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  const resource = new URL(request.url).searchParams.get('resource') || 'summary'
  const path = resource === 'users' ? '/api/v1/admin/users' : '/api/v1/admin/summary'
  try {
    const { response, payload } = await backendRequest(path, { headers: { Authorization: `Bearer ${token}` } })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Ошибка админ-панели' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Admin API временно недоступен' }, { status: 503 })
  }
}

export async function PATCH(request) {
  const token = await adminToken()
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  const body = await request.json()
  let path
  if (body.action === 'set_user_status') {
    path = `/api/v1/admin/users/${encodeURIComponent(body.user_id)}/status?active=${body.active ? 'true' : 'false'}`
  } else if (body.action === 'set_plan') {
    path = `/api/v1/admin/workspaces/${encodeURIComponent(body.workspace_id)}/plan?plan_code=${encodeURIComponent(body.plan_code)}`
  } else {
    return NextResponse.json({ error: 'Неизвестное действие' }, { status: 400 })
  }
  try {
    const { response, payload } = await backendRequest(path, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` } })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Действие не выполнено' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Admin API временно недоступен' }, { status: 503 })
  }
}
