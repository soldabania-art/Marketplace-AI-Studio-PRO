import {cookies} from 'next/headers'
import {NextResponse} from 'next/server'
import {backendRequest} from '../../../../../lib/backend'

export async function DELETE(request,{params}){
  const jar=await cookies();const session=jar.get('mai_session')?.value
  if(!session)return NextResponse.json({error:'Требуется вход'},{status:401})
  const storeId=new URL(request.url).searchParams.get('store_id')
  if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
  try{
    const {mapping_id:mappingId}=await params
    const {response,payload}=await backendRequest(`/api/v1/profit-center/cost-import-mappings/${encodeURIComponent(mappingId)}?store_id=${encodeURIComponent(storeId)}`,{method:'DELETE',headers:{Authorization:`Bearer ${session}`}})
    if(!response.ok)return NextResponse.json({error:payload?.detail||'Не удалось удалить схему'},{status:response.status})
    return new NextResponse(null,{status:204})
  }catch{return NextResponse.json({error:'Не удалось обработать запрос.'},{status:400})}
}
