import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST() {
  const cookieStore = await cookies()
  const token = cookieStore.get('mai_session')?.value

  if (token) {
    try {
      await backendRequest('/api/v1/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      // Local cookie is still cleared even if the backend is temporarily unavailable.
    }
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.set('mai_session', '', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 0,
  })
  return response
}
