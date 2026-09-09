import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

async function token(){const jar=await cookies();return jar.get('mai_session')?.value}

export async function GET(request){
  const session=await token()
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url)
  const storeId=searchParams.get('store_id'); const periodDays=searchParams.get('period_days')||'30'
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {response,payload}=await backendRequest(`/api/v1/profit-center?store_id=${encodeURIComponent(storeId)}&period_days=${encodeURIComponent(periodDays)}`,{headers:{Authorization:`Bearer ${session}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить Profit Center'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Profit Center временно недоступен.'},{status:503})}
}

export async function POST(request){
  const session=await token()
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const body=await request.json()
    const {response,payload}=await backendRequest('/api/v1/profit-center/sync',{method:'POST',headers:{Authorization:`Bearer ${session}`},body:JSON.stringify(body)})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось запустить синхронизацию'},{status:response.status})
    return NextResponse.json(payload,{status:202})
  }catch{return NextResponse.json({error:'Не удалось обработать запрос.'},{status:400})}
}
