import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET(request){
  const token=(await cookies()).get('mai_session')?.value
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{const {response,payload}=await backendRequest(`/api/v1/support/incidents?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${token}`}});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось загрузить инциденты'},{status:response.status})}catch{return NextResponse.json({error:'Контур инцидентов временно недоступен.'},{status:503})}
}

export async function POST(request){
  const token=(await cookies()).get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{const body=await request.json();const {response,payload}=await backendRequest('/api/v1/support/incidents',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body)});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось зарегистрировать инцидент'},{status:response.status})}catch{return NextResponse.json({error:'Не удалось обработать сообщение.'},{status:400})}
}
