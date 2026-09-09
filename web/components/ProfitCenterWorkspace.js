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
  const [taxBasis,setTaxBasis]=useState('gross_sales')
  const [taxRate,setTaxRate]=useState('')
  const [taxNote,setTaxNote]=useState('')
  const [taxConfirmed,setTaxConfirmed]=useState(false)
  const [taxSaving,setTaxSaving]=useState(false)

  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setBusy(true); setNotice('')
    try{
      const response=await fetch(`/api/profit-center?store_id=${encodeURIComponent(storeId)}&period_days=${periodDays}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось загрузить финансовые данные.')
      setData(payload)
      setCosts(Object.fromEntries((payload.products||[]).map(item=>[item.nm_id,item.cogs_per_unit||''])))
      setTaxBasis(payload.tax?.basis||'gross_sales')
      setTaxRate(payload.tax?.rate_percent||'')
      setTaxNote(payload.tax?.note||'')
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
      setNotice('Финансовый отчёт и реклама WB поставлены в очередь. Большие периоды загружаются безопасными пакетами с учётом лимитов WB.')
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

  async function saveTax(){
    if(!taxConfirmed){setNotice('Подтвердите ставку и налоговую базу по данным бухгалтера или налогового учёта.');return}
    setTaxSaving(true); setNotice('')
    try{
      const response=await fetch('/api/profit-center/tax',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,basis:taxBasis,rate_percent:taxRate,note:taxNote,confirmed:true})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось сохранить налоговые настройки.')
      setTaxConfirmed(false); setNotice('Налоговая база и ставка сохранены как подтверждённые.'); await load()
    }catch(error){setNotice(error.message)}finally{setTaxSaving(false)}
  }

  const metrics=useMemo(()=>data?[
    ['Продажи по отчёту',data.amounts.gross],
    ['Расходы на рекламу',data.advertising?.spend],
    ['Налоговый резерв',data.tax?.reserve],
    [data.profit_status==='complete'?'Расчётная прибыль':'Вклад до рекламы и налога',data.final_profit??data.contribution_before_tax_ads],
  ]:[],[data])

  return <main className="workPage profitCenterPage">
    <div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/profitability" className="ghostBtn">Калькулятор</Link></div>
    <section className="workHero"><span className="eyebrow">ФИНАНСЫ · РЕАЛЬНЫЕ ИСТОЧНИКИ</span><h1>Profit Center</h1><p>Финансовые строки и реклама Wildberries, подтверждённая себестоимость и налоговый резерв по каждому SKU. Неполный расчёт всегда явно помечен.</p></section>
    <section className="workPanel profitToolbar"><div><b>{storeLoading?'Загружаем магазин…':storeName||'Магазин не выбран'}</b><span>{data?.period?`${data.period.date_from} — ${data.period.date_to}`:'Выберите подключённый магазин'}</span></div><label>Период<select value={periodDays} onChange={event=>setPeriodDays(event.target.value)}><option value="7">7 дней</option><option value="30">30 дней</option><option value="90">90 дней</option></select></label><button className="ghostBtn" onClick={load} disabled={busy||!storeId}><RefreshCw size={16}/>{busy?' Загружаем…':' Обновить экран'}</button><button className="primaryBtn" onClick={sync} disabled={syncing||!storeId}><RefreshCw size={16}/>{syncing?' В очереди…':' Получить отчёт WB'}</button></section>
    {(storeError||notice)&&<div className="sectionNotice"><CircleAlert size={17}/>{storeError||notice}</div>}
    {data&&<>
      <section className="profitMetrics">{metrics.map(([label,value])=><article className="workPanel" key={label}><span>{label}</span><strong>{rubles(value)}</strong></article>)}</section>
      <section className="workPanel sourcePanel"><div><h2>Полнота расчёта</h2><p>{data.warning}</p></div><div className="sourceGrid">{Object.entries(sourceLabels).map(([key,label])=><div className={data.completeness[key]?'ready':'missing'} key={key}>{data.completeness[key]?<CheckCircle2 size={18}/>:<CircleAlert size={18}/>}<span>{label}</span><b>{data.completeness[key]?'готово':'не подключено'}</b></div>)}</div><div className="formulaLine"><ShieldCheck size={18}/><span>{data.formula}</span></div>{data.completeness.unallocated_financial_lines>0&&<small>Финансовых строк без nmId: {data.completeness.unallocated_financial_lines}. Они входят в итог магазина, но не распределены по товарам.</small>}{data.completeness.unallocated_advertising_lines>0&&<small>Рекламных строк без nmId: {data.completeness.unallocated_advertising_lines}. Они учтены только в итоге магазина.</small>}</section>
      <section className="workPanel taxEditor"><div><span className="eyebrow">ПОДТВЕРЖДЁННЫЙ НАЛОГОВЫЙ РЕЗЕРВ</span><h2>Налоговая база магазина</h2><p>Это управленческий резерв, не налоговая декларация. Выберите вариант только по данным вашего бухгалтера или налогового учёта.</p></div><label>База<select value={taxBasis} onChange={event=>setTaxBasis(event.target.value)}><option value="gross_sales">Продажи по отчёту WB</option><option value="wb_payout">WB к перечислению</option></select></label><label>Ставка, %<input type="number" min="0" max="100" step="0.01" value={taxRate} onChange={event=>setTaxRate(event.target.value)} placeholder="Например 6"/></label><label>Комментарий<input value={taxNote} maxLength={500} onChange={event=>setTaxNote(event.target.value)} placeholder="Режим и источник ставки"/></label><label className="taxConfirm"><input type="checkbox" checked={taxConfirmed} onChange={event=>setTaxConfirmed(event.target.checked)}/><span>Параметры проверены</span></label><button className="costSave" onClick={saveTax} disabled={taxSaving||taxRate===''||!storeId}><Save size={15}/>{taxSaving?'Сохраняем':'Сохранить налог'}</button></section>
      <section className="workPanel productProfit"><div className="profitTableHead"><div><h2>P&amp;L по SKU</h2><p>Себестоимость вводится вручную и становится фактом только после подтверждения.</p></div><span>{data.source_line_count} строк источника</span></div>
        {(data.products||[]).length?<div className="profitRows">{data.products.map(item=><article key={item.nm_id}><div className="profitIdentity"><strong>{item.title}</strong><span>{item.vendor_code||'без артикула'} · nmId {item.nm_id}</span></div><div><span>WB к перечислению</span><b>{rubles(item.amounts.payout)}</b></div><div><span>Шт.</span><b>{item.amounts.net_units}</b></div><div><span>Себестоимость / шт.</span><input type="number" min="0.01" step="0.01" value={costs[item.nm_id]??''} onChange={event=>setCosts(current=>({...current,[item.nm_id]:event.target.value}))} placeholder="Введите ₽"/></div><label className="costConfirm"><input type="checkbox" checked={Boolean(confirmed[item.nm_id])} onChange={event=>setConfirmed(current=>({...current,[item.nm_id]:event.target.checked}))}/><span>Из документов</span></label><button className="costSave" onClick={()=>saveCost(item.nm_id)} disabled={saving===String(item.nm_id)||!costs[item.nm_id]}><Save size={15}/>{saving===String(item.nm_id)?'Сохраняем':'Сохранить'}</button><div className="contribution"><span>Реклама {rubles(item.advertising_spend)} · налог {rubles(item.tax_reserve)}</span><b>{item.final_profit===null?`До рекламы и налога ${rubles(item.contribution_before_tax_ads)}`:`Прибыль ${rubles(item.final_profit)}`}</b></div></article>)}</div>:<div className="profitEmpty">Финансовых строк за период пока нет. Нажмите «Получить отчёт WB».</div>}
      </section>
    </>}
  </main>
}
