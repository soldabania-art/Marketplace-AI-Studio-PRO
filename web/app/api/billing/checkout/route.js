import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request) {
  const session = (await cookies()).get('mai_session')?.value
  if (!session) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  try {
    const body = await request.json()
    const { response, payload } = await backendRequest('/api/v1/billing/checkout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${session}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Не удалось начать оплату' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Платёжный сервис временно недоступен.' }, { status: 503 })
  }
}
