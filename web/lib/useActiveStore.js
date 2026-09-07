'use client'

import { useEffect, useState } from 'react'

export const STORE_KEY='mai_store_id'
export const STORE_EVENT='mai:store-changed'

export function setActiveStoreId(storeId){
  if(typeof window==='undefined') return
  if(storeId) window.localStorage.setItem(STORE_KEY,storeId)
  else window.localStorage.removeItem(STORE_KEY)
  window.dispatchEvent(new CustomEvent(STORE_EVENT,{detail:{store_id:storeId||''}}))
}

export function getActiveStoreId(){
  if(typeof window==='undefined') return ''
  return window.localStorage.getItem(STORE_KEY)||''
}

export function useActiveStore(){
  const [storeId,setStoreId]=useState('')
  const [storeName,setStoreName]=useState('')
  const [stores,setStores]=useState([])
  const [loading,setLoading]=useState(true)

  async function refresh(preferredId=''){
    setLoading(true)
    try{
      const response=await fetch('/api/stores',{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok) throw new Error(payload.error||'Не удалось загрузить магазины')
      const rows=payload.stores||[]
      setStores(rows)
      const saved=preferredId||getActiveStoreId()
      const next=rows.some(x=>x.id===saved)?saved:(rows[0]?.id||'')
      setStoreId(next)
      setStoreName(rows.find(x=>x.id===next)?.name||'')
      if(next&&next!==getActiveStoreId()) setActiveStoreId(next)
      return {storeId:next,stores:rows}
    } finally { setLoading(false) }
  }

  useEffect(()=>{
    let alive=true
    refresh().catch(()=>alive&&setLoading(false))
    function changed(event){
      const next=event?.detail?.store_id||getActiveStoreId()
      if(!alive) return
      setStoreId(next)
      setStoreName(stores.find(x=>x.id===next)?.name||'')
      if(!stores.some(x=>x.id===next)) refresh(next).catch(()=>{})
    }
    window.addEventListener(STORE_EVENT,changed)
    return ()=>{alive=false;window.removeEventListener(STORE_EVENT,changed)}
  },[stores.length])

  function select(storeId){
    setActiveStoreId(storeId)
    setStoreId(storeId)
    setStoreName(stores.find(x=>x.id===storeId)?.name||'')
  }

  return {storeId,storeName,stores,loading,select,refresh}
}
