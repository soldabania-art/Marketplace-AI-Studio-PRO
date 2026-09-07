import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET(){
  const store=await cookies()
  const token=store.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход в аккаунт.'},{status:401})
  try{
    const {response,payload}=await backendRequest('/api/v1/push/config',{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось получить настройки PUSH.'},{status:response.status})
    return NextResponse.json(payload)
  }catch{
    return NextResponse.json({error:'Сервис PUSH пока недоступен.'},{status:503})
  }
}
