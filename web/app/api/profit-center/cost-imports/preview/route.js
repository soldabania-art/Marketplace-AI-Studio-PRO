import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../lib/backend'

export async function POST(request){
  const jar=await cookies(); const session=jar.get('mai_session')?.value
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const body=await request.json()
    const {response,payload}=await backendRequest('/api/v1/profit-center/cost-imports/preview',{method:'POST',headers:{Authorization:`Bearer ${session}`},body:JSON.stringify(body)})
    if(!response.ok){const detail=payload?.detail;return NextResponse.json({error:typeof detail==='string'?detail:(detail?.message||'Не удалось проверить импорт'),details:typeof detail==='object'?detail:null},{status:response.status})}
    return NextResponse.json(payload,{status:201})
  }catch{return NextResponse.json({error:'Не удалось обработать импорт.'},{status:400})}
}
