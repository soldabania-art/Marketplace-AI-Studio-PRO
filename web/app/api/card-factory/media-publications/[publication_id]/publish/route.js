import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../../lib/backend'

export async function POST(request,{params}){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const {publication_id}=await params; const body=await request.json()
  try{
    const {response,payload}=await backendRequest(`/api/v1/card-factory/media-publications/${encodeURIComponent(publication_id)}/publish`,{method:'POST',body:JSON.stringify(body),timeoutMs:120000,headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'WB не принял изображение'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Публикация изображения временно недоступна.'},{status:503})}
}
