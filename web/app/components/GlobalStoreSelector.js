'use client'

import { useEffect, useMemo, useState } from 'react'
import { Building2, ChevronDown } from 'lucide-react'

const STORE_KEY='mai_store_id'

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
        const saved=typeof window!=='undefined'?window.localStorage.getItem(STORE_KEY):''
        const selected=rows.some(x=>x.id===saved)?saved:(rows[0]?.id||'')
        setActiveId(selected)
        if(selected&&typeof window!=='undefined') window.localStorage.setItem(STORE_KEY,selected)
      })
      .catch(e=>alive&&setError(e.message))
    return ()=>{alive=false}
  },[])

  useEffect(()=>{
    function sync(event){
      const next=event?.detail?.store_id||window.localStorage.getItem(STORE_KEY)||''
      if(next&&stores.some(x=>x.id===next)) setActiveId(next)
    }
    window.addEventListener('mai:store-changed',sync)
    return ()=>window.removeEventListener('mai:store-changed',sync)
  },[stores])

  const active=useMemo(()=>stores.find(x=>x.id===activeId),[stores,activeId])

  function selectStore(nextId){
    setActiveId(nextId)
    window.localStorage.setItem(STORE_KEY,nextId)
    window.dispatchEvent(new CustomEvent('mai:store-changed',{detail:{store_id:nextId}}))
  }

  if(!stores.length) return null

  return <div className="globalStoreSelector" title={error||'Активный магазин для всех рабочих разделов'}>
    <Building2 size={16}/>
    <div className="globalStoreSelectorCopy"><span>АКТИВНЫЙ МАГАЗИН</span><strong>{active?.name||'Выберите магазин'}</strong></div>
    <div className="globalStoreSelectorControl"><select aria-label="Активный магазин" value={activeId} onChange={e=>selectStore(e.target.value)}>{stores.map(store=><option key={store.id} value={store.id}>{store.name}{store.client_name?` · ${store.client_name}`:''}</option>)}</select><ChevronDown size={14}/></div>
  </div>
}

export { STORE_KEY }
