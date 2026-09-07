import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET(request){
  const store=await cookies(); const token=store.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Подключите аккаунт и магазин, чтобы загрузить комиссию автоматически.'},{status:401})
  const {searchParams}=new URL(request.url)
  const marketplace=searchParams.get('marketplace')||'wildberries'
  const sku=searchParams.get('sku')||''
  try{
    const qs=new URLSearchParams({marketplace,sku})
    const {response,payload}=await backendRequest(`/api/v1/marketplaces/commission?${qs.toString()}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось получить комиссию маркетплейса'},{status:response.status})
    return NextResponse.json(payload)
  }catch(error){return NextResponse.json({error:'Сервис комиссий пока недоступен.'},{status:503})}
}
