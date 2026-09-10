import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET() {
  const session = (await cookies()).get('mai_session')?.value
  if (!session) return NextResponse.json({ error: 'Требуется вход' }, { status: 401 })
  try {
    const { response, payload } = await backendRequest('/api/v1/billing/activation', {
      headers: { Authorization: `Bearer ${session}` },
    })
    return NextResponse.json(response.ok ? payload : { error: payload?.detail || 'Не удалось определить следующий шаг' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: 'Маршрут активации временно недоступен.' }, { status: 503 })
  }
}
