import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export async function GET(request){
 const token=(await cookies()).get('mai_session')?.value
 if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
 const storeId=new URL(request.url).searchParams.get('store_id');const qs=storeId?`?store_id=${encodeURIComponent(storeId)}`:''
 try{const {response,payload}=await backendRequest(`/api/v1/integrations/catalog${qs}`,{headers:{Authorization:`Bearer ${token}`}});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось загрузить каталог интеграций'},{status:response.status})}
 catch{return NextResponse.json({error:'Integration Hub временно недоступен.'},{status:503})}
}
