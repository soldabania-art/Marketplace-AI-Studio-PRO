import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../lib/backend'

export async function GET(request,{params}){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const {nm_id:nmId}=await params
  const {searchParams}=new URL(request.url); const storeId=searchParams.get('store_id')
  if(!storeId) return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {response,payload}=await backendRequest(`/api/v1/card-factory/cards/${encodeURIComponent(nmId)}?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось загрузить карточку'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Данные карточки временно недоступны.'},{status:503})}
}
