import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function POST(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const body=await request.json()
  try{
    const {response,payload}=await backendRequest('/api/v1/beginner/analyze-photo',{method:'POST',body:JSON.stringify(body),timeoutMs:75000,headers:{Authorization:`Bearer ${token}`}})
    if(!response.ok) return NextResponse.json({error:payload?.detail||'Не удалось проанализировать фотографию'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'AI-сервис временно недоступен.'},{status:503})}
}
