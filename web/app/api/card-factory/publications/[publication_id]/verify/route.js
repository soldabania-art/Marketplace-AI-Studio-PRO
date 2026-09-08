import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../../lib/backend'

export async function POST(request,{params}){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const {publication_id:publicationId}=await params
  const body=await request.json()
  try{
    const {response,payload}=await backendRequest(`/api/v1/card-factory/publications/${encodeURIComponent(publicationId)}/verify`,{method:'POST',body:JSON.stringify(body),timeoutMs:45000,headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось проверить карточку в WB'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Контрольная проверка WB временно недоступна.'},{status:503})}
}
