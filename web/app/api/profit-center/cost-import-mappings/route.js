import {cookies} from 'next/headers'
import {NextResponse} from 'next/server'
import {backendRequest} from '../../../../lib/backend'

async function session(){const jar=await cookies();return jar.get('mai_session')?.value}

export async function GET(request){
  const token=await session();if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {response,payload}=await backendRequest(`/api/v1/profit-center/cost-import-mappings?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось загрузить схемы'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Схемы импорта временно недоступны.'},{status:503})}
}

export async function POST(request){
  const token=await session();if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const body=await request.json()
    const {response,payload}=await backendRequest('/api/v1/profit-center/cost-import-mappings',{method:'POST',headers:{Authorization:`Bearer ${token}`},body:JSON.stringify(body)})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось сохранить схему'},{status:response.status})
    return NextResponse.json(payload,{status:201})
  }catch{return NextResponse.json({error:'Не удалось обработать схему.'},{status:400})}
}
