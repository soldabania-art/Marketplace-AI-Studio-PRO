import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function sessionToken(){
  const store=await cookies()
  return store.get('mai_session')?.value
}

export async function GET(){
  const token=await sessionToken()
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const {response,payload}=await backendRequest('/api/v1/stores',{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось загрузить магазины'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис магазинов временно недоступен.'},{status:503})}
}

export async function POST(request){
  const token=await sessionToken()
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные магазина'},{status:400})}
  try{
    const {response,payload}=await backendRequest('/api/v1/stores',{
      method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body),
    })
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось создать магазин'},{status:response.status})
    return NextResponse.json(payload,{status:201})
  }catch{return NextResponse.json({error:'Сервис магазинов временно недоступен.'},{status:503})}
}
