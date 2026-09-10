import { createHash } from 'crypto'
import { get } from '@vercel/blob'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../../lib/backend'

export const runtime='nodejs'
export const dynamic='force-dynamic'
function safeFilename(value){return String(value||'document').replace(/[\r\n"\\/]/g,'_').slice(0,240)}
export async function GET(_request,{params}){
 const token=(await cookies()).get('mai_session')?.value
 if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
 const blobToken=process.env.DOCUMENT_BLOB_READ_WRITE_TOKEN
 if(!blobToken)return NextResponse.json({error:'Закрытое хранилище документов ещё не подключено.'},{status:503})
 try{
  const {document_id:documentId}=await params
  const authorized=await backendRequest(`/api/v1/document-vault/documents/${encodeURIComponent(documentId)}/download-authorize`,{headers:{Authorization:`Bearer ${token}`}})
  if(!authorized.response.ok)return NextResponse.json({error:authorized.payload?.detail||'Документ недоступен'},{status:authorized.response.status})
  const result=await get(authorized.payload.storage_path,{access:'private',token:blobToken,useCache:false})
  if(!result||result.statusCode!==200||!result.stream)return NextResponse.json({error:'Файл не найден в хранилище'},{status:404})
  const chunks=[];for await(const chunk of result.stream)chunks.push(Buffer.from(chunk));const bytes=Buffer.concat(chunks)
  const digest=createHash('sha256').update(bytes).digest('hex')
  if(digest!==authorized.payload.content_sha256)return NextResponse.json({error:'Проверка целостности документа не пройдена'},{status:409})
  const filename=safeFilename(authorized.payload.display_name)
  return new NextResponse(bytes,{headers:{'Content-Type':authorized.payload.content_type,'Content-Length':String(bytes.length),'Content-Disposition':`attachment; filename="document"; filename*=UTF-8''${encodeURIComponent(filename)}`,'Cache-Control':'private, no-store, max-age=0','X-Content-Type-Options':'nosniff'}})
 }catch{return NextResponse.json({error:'Скачивание временно недоступно.'},{status:503})}
}
