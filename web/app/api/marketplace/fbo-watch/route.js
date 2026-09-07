import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request){
  const store=await cookies()
  const token=store.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Войдите в аккаунт, чтобы включить мониторинг.'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные настройки мониторинга.'},{status:400})}
  try{
    const {response,payload}=await backendRequest('/api/v1/fbo/watch',{
      method:'POST',
      headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
      body:JSON.stringify(body),
    })
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось сохранить мониторинг.'},{status:response.status})
    return NextResponse.json(payload)
  }catch{
    return NextResponse.json({error:'Сервис мониторинга пока недоступен.'},{status:503})
  }
}
