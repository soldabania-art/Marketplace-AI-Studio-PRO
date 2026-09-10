import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function proxy(request,method){const token=(await cookies()).get('mai_session')?.value;if(!token)return NextResponse.json({error:'Требуется вход'},{status:401});const storeId=new URL(request.url).searchParams.get('store_id');if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400});try{const {response,payload}=await backendRequest(`/api/v1/reviews/analysis?store_id=${encodeURIComponent(storeId)}`,{method,headers:{Authorization:`Bearer ${token}`}});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось выполнить AI-анализ'},{status:response.status})}catch{return NextResponse.json({error:'AI-анализ временно недоступен.'},{status:503})}}
export async function GET(request){return proxy(request,'GET')}
export async function POST(request){return proxy(request,'POST')}
