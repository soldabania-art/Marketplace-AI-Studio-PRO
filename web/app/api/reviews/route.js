import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

export async function GET(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id'); const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{const {response,payload}=await backendRequest(`/api/v1/reviews${qs}`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить отзывы'},{status:response.status});return NextResponse.json(payload)}
  catch{return NextResponse.json({error:'Данные отзывов временно недоступны.'},{status:503})}
}
