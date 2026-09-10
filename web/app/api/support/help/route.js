import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request){const token=(await cookies()).get('mai_session')?.value;if(!token)return NextResponse.json({error:'Требуется вход'},{status:401});try{const body=await request.json();const {response,payload}=await backendRequest('/api/v1/support/help',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body)});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось найти подтверждённый ответ'},{status:response.status})}catch{return NextResponse.json({error:'Контур базы знаний временно недоступен.'},{status:503})}}
