import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function forward(method,request){
  const store=await cookies()
  const token=store.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход в аккаунт.'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные PUSH.'},{status:400})}
  try{
    const {response,payload}=await backendRequest('/api/v1/push/subscriptions',{
      method,
      headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
      body:JSON.stringify(body),
    })
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось сохранить PUSH-подписку.'},{status:response.status})
    return NextResponse.json(payload)
  }catch{
    return NextResponse.json({error:'Сервис PUSH пока недоступен.'},{status:503})
  }
}

export async function POST(request){return forward('POST',request)}
export async function DELETE(request){return forward('DELETE',request)}
