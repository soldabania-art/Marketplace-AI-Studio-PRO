'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

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

export function useActiveStore(enabled=true){
  const [storeId,setStoreId]=useState('')
  const [storeName,setStoreName]=useState('')
  const [stores,setStores]=useState([])
  const [workspaces,setWorkspaces]=useState([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const storesRef=useRef([])

  const applyStore=useCallback((nextId,rows=storesRef.current)=>{
    const next=rows.some(x=>x.id===nextId)?nextId:(rows[0]?.id||'')
    setStoreId(next)
    setStoreName(rows.find(x=>x.id===next)?.name||'')
    return next
  },[])

  const refresh=useCallback(async(preferredId='')=>{
    if(!enabled){
      setLoading(false)
      return {storeId:'',stores:[]}
    }
    setLoading(true); setError('')
    try{
      const response=await fetch('/api/stores',{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok) throw new Error(payload.error||'Не удалось загрузить магазины')
      const rows=payload.stores||[]
      const workspaceRows=payload.workspaces||[]
      storesRef.current=rows
      setStores(rows)
      setWorkspaces(workspaceRows)
      const saved=preferredId||getActiveStoreId()
      const next=applyStore(saved,rows)
      if(next&&next!==getActiveStoreId()) setActiveStoreId(next)
      return {storeId:next,stores:rows}
    }catch(e){
      setError(e.message||'Не удалось загрузить магазины')
      throw e
    }finally{setLoading(false)}
  },[applyStore,enabled])

  useEffect(()=>{
    if(!enabled){
      setLoading(false)
      return
    }
    let alive=true
    refresh().catch(()=>{})
    function changed(event){
      if(!alive) return
      const next=event?.detail?.store_id||getActiveStoreId()
      const rows=storesRef.current
      if(rows.some(x=>x.id===next)) applyStore(next,rows)
      else refresh(next).catch(()=>{})
    }
    window.addEventListener(STORE_EVENT,changed)
    return ()=>{alive=false;window.removeEventListener(STORE_EVENT,changed)}
  },[applyStore,enabled,refresh])

  function select(nextId){
    const next=applyStore(nextId)
    setActiveStoreId(next)
  }

  const activeStore=stores.find(item=>item.id===storeId)
  const activeWorkspace=workspaces.find(item=>item.id===activeStore?.workspace_id)
  return {storeId,storeName,stores,loading,error,select,refresh,
    role:activeWorkspace?.role||'',canManageStore:Boolean(activeWorkspace?.can_manage_stores)}
}
