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
  const url = new URL(request.url)
  const resource = url.searchParams.get('resource') || 'summary'
  let path
  if (resource === 'overview') path = '/api/v1/admin/overview'
  else if (resource === 'users') path = '/api/v1/admin/users'
  else if (resource === 'team') path = '/api/v1/admin/team'
  else if (resource === 'jobs') {
    const status = url.searchParams.get('status')
    path = `/api/v1/admin/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`
  } else path = '/api/v1/admin/summary'
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

export async function POST(request) {
  const token = await adminToken()
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  const body = await request.json()
  let path
  let payload
  if (body.action === 'requeue_job' && body.job_id) {
    path = `/api/v1/admin/jobs/${encodeURIComponent(body.job_id)}/requeue`
  } else if (body.action === 'grant_project_manager' && body.user_id) {
    path = '/api/v1/admin/team/grants'
    payload = JSON.stringify({ user_id: body.user_id, role: 'project_manager' })
  } else return NextResponse.json({ error: 'Неизвестное действие' }, { status: 400 })
  try {
    const { response, payload: result } = await backendRequest(path, { method: 'POST', headers: { Authorization: `Bearer ${token}`, ...(payload ? { 'Content-Type': 'application/json' } : {}) }, body: payload })
    return NextResponse.json(response.ok ? result : { error: result?.detail || 'Действие не выполнено' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Admin API временно недоступен' }, { status: 503 })
  }
}

export async function DELETE(request) {
  const token = await adminToken()
  if (!token) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  const userId = new URL(request.url).searchParams.get('user_id')
  if (!userId) return NextResponse.json({ error: 'Не выбран пользователь' }, { status: 400 })
  try {
    const { response, payload } = await backendRequest(`/api/v1/admin/team/grants/${encodeURIComponent(userId)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Доступ не отозван' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Admin API временно недоступен' }, { status: 503 })
  }
}
