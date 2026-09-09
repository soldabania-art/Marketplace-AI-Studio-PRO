'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, CheckCircle2, CircleAlert, RefreshCw, Save, ShieldCheck } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const rubles=value=>value===null||value===undefined?'—':`${Number(value).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} ₽`
const sourceLabels={wb_finance:'Финансовый отчёт WB',cogs:'Себестоимость',advertising:'Реклама',tax:'Налоги'}

export default function ProfitCenterWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
  const [periodDays,setPeriodDays]=useState('30')
  const [data,setData]=useState(null)
  const [busy,setBusy]=useState(false)
  const [syncing,setSyncing]=useState(false)
  const [notice,setNotice]=useState('')
  const [costs,setCosts]=useState({})
  const [confirmed,setConfirmed]=useState({})
  const [saving,setSaving]=useState('')

  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setBusy(true); setNotice('')
    try{
      const response=await fetch(`/api/profit-center?store_id=${encodeURIComponent(storeId)}&period_days=${periodDays}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось загрузить финансовые данные.')
      setData(payload)
      setCosts(Object.fromEntries((payload.products||[]).map(item=>[item.nm_id,item.cogs_per_unit||''])))
    }catch(error){setData(null);setNotice(error.message)}finally{setBusy(false)}
  },[storeId,periodDays])

  useEffect(()=>{load()},[load])

  async function sync(){
    if(!storeId)return
    setSyncing(true); setNotice('')
    try{
      const response=await fetch('/api/profit-center',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,period_days:Number(periodDays)})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось запустить синхронизацию.')
      setNotice('Отчёт WB поставлен в очередь. Из-за лимита WB большие отчёты загружаются постранично — по одной странице в минуту.')
      window.setTimeout(load,2500)
    }catch(error){setNotice(error.message)}finally{setSyncing(false)}
  }

  async function saveCost(nmId){
    const value=costs[nmId]
    if(!confirmed[nmId]){setNotice('Подтвердите, что себестоимость взята из ваших документов.');return}
    setSaving(String(nmId)); setNotice('')
    try{
      const response=await fetch(`/api/profit-center/costs/${nmId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,cogs_rub:value,confirmed:true})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось сохранить себестоимость.')
      setConfirmed(current=>({...current,[nmId]:false}))
      setNotice(`Себестоимость товара ${nmId} сохранена как подтверждённая.`)
      await load()
    }catch(error){setNotice(error.message)}finally{setSaving('')}
  }

  const metrics=useMemo(()=>data?[
    ['Продажи по отчёту',data.amounts.gross],
    ['WB к перечислению',data.amounts.payout],
    ['Известные расходы WB',String((Number(data.amounts.logistics||0)+Number(data.amounts.acquiring||0)+Number(data.amounts.storage||0)+Number(data.amounts.acceptance||0)+Number(data.amounts.penalty||0)+Number(data.amounts.deduction||0)-Number(data.amounts.additional_payment||0)).toFixed(2))],
    ['Вклад до налогов и рекламы',data.contribution_before_tax_ads],
  ]:[],[data])

  return <main className="workPage profitCenterPage">
    <div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/profitability" className="ghostBtn">Калькулятор</Link></div>
    <section className="workHero"><span className="eyebrow">ФИНАНСЫ · РЕАЛЬНЫЕ ИСТОЧНИКИ</span><h1>Profit Center</h1><p>Финансовые строки Wildberries и подтверждённая себестоимость по каждому SKU. TROVENDI не называет показатель чистой прибылью, пока не подключены реклама и налоги.</p></section>
    <section className="workPanel profitToolbar"><div><b>{storeLoading?'Загружаем магазин…':storeName||'Магазин не выбран'}</b><span>{data?.period?`${data.period.date_from} — ${data.period.date_to}`:'Выберите подключённый магазин'}</span></div><label>Период<select value={periodDays} onChange={event=>setPeriodDays(event.target.value)}><option value="7">7 дней</option><option value="30">30 дней</option><option value="90">90 дней</option></select></label><button className="ghostBtn" onClick={load} disabled={busy||!storeId}><RefreshCw size={16}/>{busy?' Загружаем…':' Обновить экран'}</button><button className="primaryBtn" onClick={sync} disabled={syncing||!storeId}><RefreshCw size={16}/>{syncing?' В очереди…':' Получить отчёт WB'}</button></section>
    {(storeError||notice)&&<div className="sectionNotice"><CircleAlert size={17}/>{storeError||notice}</div>}
    {data&&<>
      <section className="profitMetrics">{metrics.map(([label,value])=><article className="workPanel" key={label}><span>{label}</span><strong>{rubles(value)}</strong></article>)}</section>
      <section className="workPanel sourcePanel"><div><h2>Полнота расчёта</h2><p>{data.warning}</p></div><div className="sourceGrid">{Object.entries(sourceLabels).map(([key,label])=><div className={data.completeness[key]?'ready':'missing'} key={key}>{data.completeness[key]?<CheckCircle2 size={18}/>:<CircleAlert size={18}/>}<span>{label}</span><b>{data.completeness[key]?'готово':'не подключено'}</b></div>)}</div><div className="formulaLine"><ShieldCheck size={18}/><span>{data.formula}</span></div>{data.completeness.unallocated_financial_lines>0&&<small>Строк без nmId: {data.completeness.unallocated_financial_lines}. Они входят в итог магазина, но не распределены по товарам.</small>}</section>
      <section className="workPanel productProfit"><div className="profitTableHead"><div><h2>P&amp;L по SKU</h2><p>Себестоимость вводится вручную и становится фактом только после подтверждения.</p></div><span>{data.source_line_count} строк источника</span></div>
        {(data.products||[]).length?<div className="profitRows">{data.products.map(item=><article key={item.nm_id}><div className="profitIdentity"><strong>{item.title}</strong><span>{item.vendor_code||'без артикула'} · nmId {item.nm_id}</span></div><div><span>WB к перечислению</span><b>{rubles(item.amounts.payout)}</b></div><div><span>Шт.</span><b>{item.amounts.net_units}</b></div><div><span>Себестоимость / шт.</span><input type="number" min="0.01" step="0.01" value={costs[item.nm_id]??''} onChange={event=>setCosts(current=>({...current,[item.nm_id]:event.target.value}))} placeholder="Введите ₽"/></div><label className="costConfirm"><input type="checkbox" checked={Boolean(confirmed[item.nm_id])} onChange={event=>setConfirmed(current=>({...current,[item.nm_id]:event.target.checked}))}/><span>Из документов</span></label><button className="costSave" onClick={()=>saveCost(item.nm_id)} disabled={saving===String(item.nm_id)||!costs[item.nm_id]}><Save size={15}/>{saving===String(item.nm_id)?'Сохраняем':'Сохранить'}</button><div className="contribution"><span>Вклад до налогов и рекламы</span><b>{rubles(item.contribution_before_tax_ads)}</b></div></article>)}</div>:<div className="profitEmpty">Финансовых строк за период пока нет. Нажмите «Получить отчёт WB».</div>}
      </section>
    </>}
  </main>
}
