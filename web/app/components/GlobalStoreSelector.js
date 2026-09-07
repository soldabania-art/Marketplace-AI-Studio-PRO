'use client'

import { useEffect, useMemo, useState } from 'react'
import { Building2, ChevronDown } from 'lucide-react'
import { getActiveStoreId, setActiveStoreId, STORE_EVENT } from '../../lib/useActiveStore'

export default function GlobalStoreSelector(){
  const [stores,setStores]=useState([])
  const [activeId,setActiveId]=useState('')
  const [error,setError]=useState('')

  useEffect(()=>{
    let alive=true
    fetch('/api/stores',{cache:'no-store'})
      .then(async response=>{
        const payload=await response.json()
        if(!response.ok) throw new Error(payload.error||'Не удалось загрузить магазины')
        if(!alive) return
        const rows=payload.stores||[]
        setStores(rows)
        const saved=getActiveStoreId()
        const selected=rows.some(x=>x.id===saved)?saved:(rows[0]?.id||'')
        setActiveId(selected)
        if(selected&&selected!==saved) setActiveStoreId(selected)
      })
      .catch(e=>alive&&setError(e.message))
    return ()=>{alive=false}
  },[])

  useEffect(()=>{
    function sync(event){
      const next=event?.detail?.store_id||getActiveStoreId()
      if(next&&stores.some(x=>x.id===next)) setActiveId(next)
    }
    window.addEventListener(STORE_EVENT,sync)
    return ()=>window.removeEventListener(STORE_EVENT,sync)
  },[stores])

  const active=useMemo(()=>stores.find(x=>x.id===activeId),[stores,activeId])

  function selectStore(nextId){
    setActiveId(nextId)
    setActiveStoreId(nextId)
  }

  if(!stores.length) return null

  return <div className="globalStoreSelector" title={error||'Активный магазин для всех рабочих разделов'}>
    <Building2 size={16}/>
    <div className="globalStoreSelectorCopy"><span>АКТИВНЫЙ МАГАЗИН</span><strong>{active?.name||'Выберите магазин'}</strong></div>
    <div className="globalStoreSelectorControl"><select aria-label="Активный магазин" value={activeId} onChange={e=>selectStore(e.target.value)}>{stores.map(store=><option key={store.id} value={store.id}>{store.name}{store.client_name?` · ${store.client_name}`:''}</option>)}</select><ChevronDown size={14}/></div>
  </div>
}
