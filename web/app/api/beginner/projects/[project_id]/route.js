import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../lib/backend'

export async function PATCH(request,{params}){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  const {project_id:projectId}=await params
  const body=await request.json()
  try{const {response,payload}=await backendRequest(`/api/v1/beginner/projects/${encodeURIComponent(projectId)}`,{method:'PATCH',body:JSON.stringify(body),headers:{Authorization:`Bearer ${token}`}});if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось обновить проект'},{status:response.status});return NextResponse.json(payload)}catch{return NextResponse.json({error:'Проект временно не сохраняется.'},{status:503})}
}
