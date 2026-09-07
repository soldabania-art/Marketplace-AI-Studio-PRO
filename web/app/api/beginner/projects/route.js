import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function token(){const jar=await cookies();return jar.get('mai_session')?.value}

export async function GET(request){
  const session=await token(); if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{const {response,payload}=await backendRequest(`/api/v1/beginner/projects?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${session}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить проекты'},{status:response.status});return NextResponse.json(payload)}catch{return NextResponse.json({error:'Проекты временно недоступны.'},{status:503})}
}

export async function POST(request){
  const session=await token(); if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const body=await request.json()
  try{const {response,payload}=await backendRequest('/api/v1/beginner/projects',{method:'POST',body:JSON.stringify(body),headers:{Authorization:`Bearer ${session}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось сохранить проект'},{status:response.status});return NextResponse.json(payload,{status:201})}catch{return NextResponse.json({error:'Проект временно не сохраняется.'},{status:503})}
}
