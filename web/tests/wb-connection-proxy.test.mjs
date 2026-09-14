import test from 'node:test'
import assert from 'node:assert/strict'
import http from 'node:http'

import {backendRequest} from '../lib/backend.js'
import {
  WB_PREFLIGHT_PROXY_TIMEOUT_MS,
  readWbState,
  reconcileUnknownWbOutcome,
  requestWbPreflight,
} from '../lib/wbConnectionProxy.mjs'

test('WB proxy budget leaves backend preflight time to return within the existing ceiling',()=>{
  assert.equal(WB_PREFLIGHT_PROXY_TIMEOUT_MS,9000)
  assert.ok(WB_PREFLIGHT_PROXY_TIMEOUT_MS<=10000)
})

test('unknown rotation keeps the candidate when GET still reports the old saved token',async()=>{
  const candidate='candidate-token-that-must-survive'
  const reconciled=await reconcileUnknownWbOutcome(
    async()=>({token_saved:true,credentials_version:4,verification:{summary:'complete'}}),
    candidate,
    'rotation',
  )
  assert.equal(reconciled.candidate,candidate)
  assert.equal(reconciled.unknown.operation,'rotation')
  assert.equal(reconciled.current.credentials_version,4)
})

test('unknown refresh labels GET data as the last saved state',async()=>{
  const reconciled=await reconcileUnknownWbOutcome(
    async()=>({token_saved:true,credentials_version:7,verification:{summary:'partial'}}),
    '',
    'refresh',
  )
  assert.equal(reconciled.unknown.operation,'refresh')
  assert.equal(reconciled.unknown.currentIsLastSavedState,true)
  assert.equal(reconciled.current.verification.summary,'partial')
})

test('unknown mutation outcome is reconciled with one status GET and no repeated POST',async()=>{
  const calls=[]
  const state=await readWbState(async(url,options)=>{
    calls.push({url,options})
    return {ok:true,json:async()=>({store_id:'store / 7',token_saved:true,sources_verified:false})}
  },'store / 7')
  assert.equal(state.token_saved,true)
  assert.deepEqual(calls,[{
    url:'/api/marketplace/wildberries?store_id=store%20%2F%207',
    options:{cache:'no-store'},
  }])
})

test('status read rejects a payload for another store',async()=>{
  await assert.rejects(
    readWbState(async()=>({ok:true,json:async()=>({store_id:'store-b'})}),'store-a'),
    /другого магазина/,
  )
})

test('proxy timeout reports unknown outcome while backend may still finish',async()=>{
  let backendFinished=false
  let finishBackend
  const backendDone=new Promise(resolve=>{finishBackend=resolve})
  const server=http.createServer(async(_request,response)=>{
    await new Promise(resolve=>setTimeout(resolve,250))
    backendFinished=true
    response.writeHead(200,{'content-type':'application/json'})
    response.end(JSON.stringify({token_saved:true}))
    finishBackend()
  })
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
  const previous=process.env.MARKETPLACE_API_URL
  process.env.MARKETPLACE_API_URL=`http://127.0.0.1:${server.address().port}`
  try{
    const result=await requestWbPreflight(backendRequest,'/slow',{method:'POST',timeoutMs:100})
    assert.deepEqual(result,{outcome:'unknown'})
    assert.equal(backendFinished,false)
    await backendDone
    assert.equal(backendFinished,true)
  }finally{
    if(previous===undefined) delete process.env.MARKETPLACE_API_URL
    else process.env.MARKETPLACE_API_URL=previous
    server.closeAllConnections()
    await new Promise(resolve=>server.close(resolve))
  }
})
