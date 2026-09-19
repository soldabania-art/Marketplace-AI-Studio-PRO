import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../lib/backend'
import {requestWbPreflight} from '../../../../../lib/wbConnectionProxy.mjs'

export async function POST(request){
  const cookieStore=await cookies()
  const token=cookieStore.get('mai_session')?.value
  if(!token) return NextResponse.json({error:'Требуется вход'},{status:401})
  const {searchParams}=new URL(request.url)
  const storeId=searchParams.get('store_id')
  const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
  try{
    const result=await requestWbPreflight(backendRequest,`/api/v1/integrations/wildberries/check${qs}`,{
      method:'POST',headers:{Authorization:`Bearer ${token}`},
    })
    if(result.outcome==='unknown') return NextResponse.json({error:'Ожидание ответа завершилось. Текущее состояние проверки нужно перечитать.',outcome_unknown:true},{status:504})
    const {response,payload}=result
    if(!response.ok){
      const detail=payload?.detail
      return NextResponse.json({error:typeof detail==='string'?detail:'Не удалось проверить источники WB'},{status:response.status})
    }
    return NextResponse.json(payload)
  }catch{return NextResponse.json({error:'Сервис проверки источников WB временно недоступен.'},{status:503})}
}
