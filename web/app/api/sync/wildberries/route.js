import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url); const storeId=searchParams.get('store_id')
  const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{
    const {response,payload}=await backendRequest(`/api/v1/sync/wildberries${qs}`,{method:'POST',headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось запустить синхронизацию WB'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис синхронизации WB временно недоступен.'},{status:503})}
}
