import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function token() {
  return (await cookies()).get('mai_session')?.value
}

export async function GET() {
  const session = await token()
  if (!session) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  try {
    const { response, payload } = await backendRequest('/api/v1/billing/subscription', {
      headers: { Authorization: `Bearer ${session}` },
    })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Не удалось загрузить тариф' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Сервис тарифа временно недоступен.' }, { status: 503 })
  }
}
