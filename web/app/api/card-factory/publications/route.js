import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url); const storeId=searchParams.get('store_id'); const nmId=searchParams.get('nm_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  const query=new URLSearchParams({store_id:storeId});if(nmId)query.set('nm_id',nmId)
  try{
    const {response,payload}=await backendRequest(`/api/v1/card-factory/publications?${query}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить историю публикаций'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'История публикаций временно недоступна.'},{status:503})}
}

export async function POST(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const body=await request.json()
  try{
    const {response,payload}=await backendRequest('/api/v1/card-factory/publications/prepare',{method:'POST',body:JSON.stringify(body),headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось подготовить сравнение'},{status:response.status})
    return NextResponse.json(payload,{status:response.status})
  }catch{return NextResponse.json({error:'Подготовка публикации временно недоступна.'},{status:503})}
}
