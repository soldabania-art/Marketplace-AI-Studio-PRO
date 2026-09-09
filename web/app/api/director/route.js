import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

export async function GET(request){
  const jar=await cookies(); const session=jar.get('mai_session')?.value
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {response,payload}=await backendRequest(`/api/v1/director?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${session}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить AI Director'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'AI Director временно недоступен.'},{status:503})}
}
