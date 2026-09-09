import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function session(){return (await cookies()).get('mai_session')?.value}

export async function GET(request){
  const token=await session()
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {response,payload}=await backendRequest(`/api/v1/agents/work-orders?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить задачи'},{status:response.status})
    return NextResponse.json(payload,{headers:{'Cache-Control':'no-store'}})
  }catch{return NextResponse.json({error:'Задачи агентов временно недоступны.'},{status:503})}
}

export async function POST(request){
  const token=await session()
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректный запрос'},{status:400})}
  try{
    const {response,payload}=await backendRequest('/api/v1/agents/work-orders',{method:'POST',headers:{Authorization:`Bearer ${token}`},body:JSON.stringify(body)})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось поставить задачу'},{status:response.status})
    return NextResponse.json(payload,{status:response.status})
  }catch{return NextResponse.json({error:'AI Director временно недоступен.'},{status:503})}
}
