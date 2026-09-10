import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

async function token(){return (await cookies()).get('mai_session')?.value}

export async function GET(request){
  const session=await token();if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id');if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{const {response,payload}=await backendRequest(`/api/v1/onboarding?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${session}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось проверить настройку'},{status:response.status});return NextResponse.json(payload)}catch{return NextResponse.json({error:'Мастер настройки временно недоступен.'},{status:503})}
}

export async function PUT(request){
  const session=await token();if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  let body;try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные профиля'},{status:400})}
  try{const {response,payload}=await backendRequest('/api/v1/onboarding/profile',{method:'PUT',headers:{Authorization:`Bearer ${session}`,'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось сохранить профиль'},{status:response.status});return NextResponse.json(payload)}catch{return NextResponse.json({error:'Мастер настройки временно недоступен.'},{status:503})}
}

export async function POST(request){
  const session=await token();if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  let body;try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные импорта'},{status:400})}
  if(!body?.store_id)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{const {response,payload}=await backendRequest(`/api/v1/onboarding/import?store_id=${encodeURIComponent(body.store_id)}`,{method:'POST',headers:{Authorization:`Bearer ${session}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось запустить импорт'},{status:response.status});return NextResponse.json(payload,{status:202})}catch{return NextResponse.json({error:'Импорт временно недоступен.'},{status:503})}
}
