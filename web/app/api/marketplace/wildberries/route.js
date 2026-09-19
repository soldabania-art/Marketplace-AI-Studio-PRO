import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'
import {requestWbPreflight} from '../../../../lib/wbConnectionProxy.mjs'

async function sessionToken(){
  const store=await cookies()
  return store.get('mai_session')?.value
}

function backendError(payload,fallback){
  const detail=payload?.detail
  if(detail&&typeof detail==='object') return {error:detail.message||fallback,...detail}
  return {error:detail||fallback}
}

export async function GET(request){
  const token=await sessionToken()
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url)
  const storeId=searchParams.get('store_id')
  const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{
    const {response,payload}=await backendRequest(`/api/v1/integrations/wildberries${qs}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json(backendError(payload,'Не удалось проверить подключение WB'),{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис подключения WB временно недоступен.'},{status:503})}
}

export async function POST(request){
  const token=await sessionToken()
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные подключения'},{status:400})}
  try{
    const result=await requestWbPreflight(backendRequest,'/api/v1/integrations/wildberries',{
      method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body),
    })
    if(result.outcome==='unknown') return NextResponse.json({error:'Ожидание ответа завершилось. Текущее состояние подключения нужно перечитать.',outcome_unknown:true},{status:504})
    const {response,payload}=result
    if(!response.ok) return NextResponse.json(backendError(payload,'Не удалось подключить Wildberries'),{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис подключения WB временно недоступен.'},{status:503})}
}

export async function DELETE(request){
  const token=await sessionToken()
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url)
  const storeId=searchParams.get('store_id')
  const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{
    const {response,payload}=await backendRequest(`/api/v1/integrations/wildberries${qs}`,{method:'DELETE',headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json(backendError(payload,'Не удалось отключить Wildberries'),{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис подключения WB временно недоступен.'},{status:503})}
}
