export const WB_PREFLIGHT_PROXY_TIMEOUT_MS = 9000

export async function requestWbPreflight(requestBackend,path,options={}){
  try{
    const completed=await requestBackend(path,{
      ...options,
      timeoutMs:options.timeoutMs??WB_PREFLIGHT_PROXY_TIMEOUT_MS,
    })
    return {outcome:'completed',...completed}
  }catch(error){
    if(error?.name==='AbortError') return {outcome:'unknown'}
    throw error
  }
}

export async function readWbState(fetchImpl,storeId){
  const response=await fetchImpl(
    `/api/marketplace/wildberries?store_id=${encodeURIComponent(storeId)}`,
    {cache:'no-store'},
  )
  const payload=await response.json()
  if(!response.ok) throw new Error(payload.error||'Не удалось перечитать состояние WB')
  return payload
}

export async function reconcileUnknownWbOutcome(readCurrent,candidate,operation){
  const current=await readCurrent()
  return {
    current,
    candidate,
    unknown:{operation,currentIsLastSavedState:true},
  }
}
