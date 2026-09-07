import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function token(){const store=await cookies(); return store.get('mai_session')?.value}

export async function GET(request){
  const session=await token()
  if(!session) return NextResponse.json({error:'Войдите в аккаунт.'},{status:401})
  const {searchParams}=new URL(request.url)
  const storeId=searchParams.get('store_id')||''
  const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{
    const {response,payload}=await backendRequest(`/api/v1/fbo/watch${qs}`,{headers:{Authorization:`Bearer ${session}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось загрузить мониторинг.'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис мониторинга пока недоступен.'},{status:503})}
}

export async function POST(request){
  const session=await token()
  if(!session) return NextResponse.json({error:'Войдите в аккаунт, чтобы включить мониторинг.'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные настройки мониторинга.'},{status:400})}
  try{
    const {response,payload}=await backendRequest('/api/v1/fbo/watch',{
      method:'POST',headers:{Authorization:`Bearer ${session}`,'Content-Type':'application/json'},body:JSON.stringify(body),
    })
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось сохранить мониторинг.'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис мониторинга пока недоступен.'},{status:503})}
}
