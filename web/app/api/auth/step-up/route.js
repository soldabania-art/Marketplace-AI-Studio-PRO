import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

async function accessToken(){
  const store=await cookies()
  return store.get('mai_session')?.value
}

async function forward(path,options={}){
  const token=await accessToken()
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  try{
    const {response,payload}=await backendRequest(path,{...options,headers:{Authorization:`Bearer ${token}`,...(options.headers||{})}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось подтвердить личность'},{status:response.status})
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис подтверждения временно недоступен.'},{status:503})}
}

export async function GET(){return forward('/api/v1/auth/step-up/status')}

export async function POST(request){
  let body
  try{body=await request.json()}catch{return NextResponse.json({error:'Некорректные данные'},{status:400})}
  return forward('/api/v1/auth/step-up',{method:'POST',body:JSON.stringify(body)})
}
