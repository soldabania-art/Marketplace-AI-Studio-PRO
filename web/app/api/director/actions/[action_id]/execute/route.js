import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../../lib/backend'

export async function POST(request,{params}){
  const jar=await cookies(); const session=jar.get('mai_session')?.value
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const {action_id:actionId}=await params; const body=await request.json()
    const {response,payload}=await backendRequest(`/api/v1/director/actions/${encodeURIComponent(actionId)}/execute`,{
      method:'POST',headers:{Authorization:`Bearer ${session}`},body:JSON.stringify(body)})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось запустить безопасное действие'},{status:response.status})
    return NextResponse.json(payload,{status:202})
  }catch{return NextResponse.json({error:'Не удалось обработать запрос.'},{status:400})}
}
