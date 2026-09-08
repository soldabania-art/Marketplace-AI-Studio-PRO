import { createHash } from 'crypto'
import { del, put } from '@vercel/blob'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { backendRequest } from '../../../../lib/backend'

export const maxDuration=180

export async function POST(request){
  const jar=await cookies(); const token=jar.get('mai_session')?.value
  if(!token)return NextResponse.json({error:'Требуется вход'},{status:401})
  if(!process.env.BLOB_READ_WRITE_TOKEN&&!(process.env.VERCEL_OIDC_TOKEN&&process.env.BLOB_STORE_ID))return NextResponse.json({error:'Хранилище изображений ещё не подключено к Vercel.'},{status:503})
  const body=await request.json()
  let blob
  try{
    const generated=await backendRequest('/api/v1/card-factory/generate-visual',{method:'POST',body:JSON.stringify(body),timeoutMs:150000,headers:{Authorization:`Bearer ${token}`}})
    if(!generated.response.ok)return NextResponse.json({error:generated.payload?.detail||'Не удалось создать изображение'},{status:generated.response.status})
    const bytes=Buffer.from(generated.payload.image_base64||'','base64')
    if(!bytes.length||bytes.length>15_000_000)return NextResponse.json({error:'AI вернул изображение недопустимого размера.'},{status:502})
    const pathname=`ai-assets/${body.store_id}/${body.nm_id}/${generated.payload.generation_id}.webp`
    blob=await put(pathname,bytes,{access:'public',contentType:'image/webp',addRandomSuffix:true,cacheControlMaxAge:31536000})
    const finalize=await backendRequest('/api/v1/card-factory/finalize-visual',{method:'POST',body:JSON.stringify({store_id:body.store_id,generation_id:generated.payload.generation_id,url:blob.url,pathname:blob.pathname,content_type:'image/webp',bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}),headers:{Authorization:`Bearer ${token}`}})
    if(!finalize.response.ok){await del(blob.url).catch(()=>{});return NextResponse.json({error:finalize.payload?.detail||'Изображение создано, но не удалось сохранить версию.'},{status:finalize.response.status})}
    return NextResponse.json({generation:finalize.payload.generation,publish_requires_confirmation:true})
  }catch(error){if(blob)await del(blob.url).catch(()=>{});return NextResponse.json({error:'Генерация или сохранение изображения временно недоступны.'},{status:503})}
}
