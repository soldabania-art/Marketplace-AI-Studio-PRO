import { createHash } from 'crypto'
import { del,put } from '@vercel/blob'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../lib/backend'

const MAX_BYTES=25_000_000
async function session(){return (await cookies()).get('mai_session')?.value}
function looksLike(bytes,type){
 if(type==='application/pdf')return bytes.subarray(0,5).toString()==='%PDF-'
 if(type==='image/png')return bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))
 if(type==='image/jpeg')return bytes[0]===0xff&&bytes[1]===0xd8&&bytes[2]===0xff
 if(type==='application/json'){try{JSON.parse(bytes.toString('utf8'));return true}catch{return false}}
 if(type==='application/xml'||type==='text/xml'){const value=bytes.toString('utf8').trimStart();return value.startsWith('<?xml')||value.startsWith('<')}
 if(type==='text/csv')return !bytes.includes(0)
 return false
}
export async function GET(request){
 const token=await session();if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
 const storeId=new URL(request.url).searchParams.get('store_id');if(!storeId)return NextResponse.json({error:'Выберите магазин'},{status:400})
 try{const {response,payload}=await backendRequest(`/api/v1/document-vault/documents?store_id=${encodeURIComponent(storeId)}`,{headers:{Authorization:`Bearer ${token}`}});return NextResponse.json(response.ok?payload:{error:payload?.detail||'Не удалось открыть сейф'},{status:response.status})}catch{return NextResponse.json({error:'Документный сейф временно недоступен.'},{status:503})}
}
export async function POST(request){
 const token=await session();if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
 const blobToken=process.env.DOCUMENT_BLOB_READ_WRITE_TOKEN;if(!blobToken)return NextResponse.json({error:'Закрытое хранилище документов ещё не подключено.'},{status:503})
 let blob
 try{
  const form=await request.formData();const file=form.get('file')
  if(!file||typeof file.arrayBuffer!=='function'||!file.size)return NextResponse.json({error:'Выберите файл'},{status:400})
  if(file.size>MAX_BYTES)return NextResponse.json({error:'Размер файла превышает 25 МБ'},{status:413})
  const bytes=Buffer.from(await file.arrayBuffer());const contentType=file.type||'application/octet-stream'
  if(!looksLike(bytes,contentType))return NextResponse.json({error:'Содержимое файла не соответствует заявленному формату.'},{status:422})
  const metadata={store_id:String(form.get('store_id')||''),display_name:String(form.get('display_name')||file.name||'Документ'),content_type:contentType,byte_size:file.size,subject_type:String(form.get('subject_type')||'seller'),document_type:String(form.get('document_type')||'other'),fulfillment_partner_id:String(form.get('fulfillment_partner_id')||'')||null,external_reference:String(form.get('external_reference')||'')}
  const authorized=await backendRequest('/api/v1/document-vault/uploads/authorize',{method:'POST',headers:{Authorization:`Bearer ${token}`},body:JSON.stringify(metadata)})
  if(!authorized.response.ok)return NextResponse.json({error:authorized.payload?.detail||'Загрузка не разрешена'},{status:authorized.response.status})
  const sha256=createHash('sha256').update(bytes).digest('hex')
  blob=await put(authorized.payload.storage_path,bytes,{access:'private',token:blobToken,contentType,addRandomSuffix:false,cacheControlMaxAge:0})
  const finalized=await backendRequest(`/api/v1/document-vault/documents/${authorized.payload.document.id}/finalize`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:JSON.stringify({content_sha256:sha256,byte_size:bytes.length})})
  if(!finalized.response.ok){await del(blob.url,{token:blobToken}).catch(()=>{});return NextResponse.json({error:finalized.payload?.detail||'Документ не удалось зарегистрировать'},{status:finalized.response.status})}
  return NextResponse.json(finalized.payload,{status:201})
 }catch{if(blob)await del(blob.url,{token:blobToken}).catch(()=>{});return NextResponse.json({error:'Загрузка документа не завершена.'},{status:503})}
}
