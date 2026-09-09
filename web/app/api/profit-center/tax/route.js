import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function PATCH(request){
  const jar=await cookies(); const session=jar.get('mai_session')?.value
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const body=await request.json()
    const {response,payload}=await backendRequest('/api/v1/profit-center/tax',{method:'PATCH',headers:{Authorization:`Bearer ${session}`},body:JSON.stringify(body)})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось сохранить налоговые настройки'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Не удалось обработать запрос.'},{status:400})}
}
