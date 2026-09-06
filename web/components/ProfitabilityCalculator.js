'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ArrowLeft, Calculator, TrendingDown, TrendingUp } from 'lucide-react'

const money = (v) => new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number.isFinite(v)?v:0)+' ₽'
const pct = (v) => `${(Number.isFinite(v)?v:0).toFixed(1)}%`

export default function ProfitabilityCalculator(){
  const [price,setPrice]=useState(1990)
  const [cogs,setCogs]=useState(650)
  const [commission,setCommission]=useState(20)
  const [logistics,setLogistics]=useState(180)
  const [ads,setAds]=useState(220)
  const [tax,setTax]=useState(6)
  const [other,setOther]=useState(60)

  const r=useMemo(()=>{
    const p=Number(price)||0, c=Number(cogs)||0, comm=p*(Number(commission)||0)/100, log=Number(logistics)||0, ad=Number(ads)||0, t=p*(Number(tax)||0)/100, o=Number(other)||0
    const costs=c+comm+log+ad+t+o
    const profit=p-costs
    const margin=p>0?profit/p*100:0
    const roi=c>0?profit/c*100:0
    const breakEven=1-((Number(commission)||0)+(Number(tax)||0))/100
    const breakEvenPrice=breakEven>0?(c+log+ad+o)/breakEven:0
    return {comm,t,costs,profit,margin,roi,breakEvenPrice}
  },[price,cogs,commission,logistics,ads,tax,other])

  const fields=[['Цена продажи',price,setPrice,'₽'],['Себестоимость',cogs,setCogs,'₽'],['Комиссия маркетплейса',commission,setCommission,'%'],['Логистика',logistics,setLogistics,'₽'],['Реклама на заказ',ads,setAds,'₽'],['Налог',tax,setTax,'%'],['Прочие расходы',other,setOther,'₽']]
  return <main className="workPage">
    <div className="workHead"><Link href="/profit" className="ghostBtn"><ArrowLeft size={16}/> Profit Center</Link><Link href="/pricing" className="ghostBtn">Тарифы</Link></div>
    <section className="workHero"><span className="eyebrow">ЮНИТ-ЭКОНОМИКА</span><h1>Калькулятор рентабельности</h1><p>Показывает чистую прибыль с единицы, маржинальность, ROI и цену безубыточности. Все значения можно менять вручную.</p></section>
    <div className="factoryGrid"><section className="workPanel formPanel"><div className="panelTitle"><h2>Исходные данные</h2><Calculator size={20}/></div>{fields.map(([label,value,setter,suffix])=><label key={label}>{label}<div className="calcInput"><input type="number" min="0" step="0.01" value={value} onChange={e=>setter(e.target.value)}/><span>{suffix}</span></div></label>)}</section>
    <section className="workPanel previewPanel"><span className="eyebrow">РЕЗУЛЬТАТ</span><div className={`profitHero ${r.profit>=0?'positive':'negative'}`}><div>{r.profit>=0?<TrendingUp size={22}/>:<TrendingDown size={22}/>}<span>Чистая прибыль с единицы</span></div><strong>{money(r.profit)}</strong></div>
    <div className="calcStats"><div><span>Маржинальность</span><strong>{pct(r.margin)}</strong></div><div><span>ROI на себестоимость</span><strong>{pct(r.roi)}</strong></div><div><span>Все расходы</span><strong>{money(r.costs)}</strong></div><div><span>Цена безубыточности</span><strong>{money(r.breakEvenPrice)}</strong></div></div>
    <div className="costBreakdown"><h3>Структура расходов</h3><div><span>Себестоимость</span><b>{money(Number(cogs)||0)}</b></div><div><span>Комиссия</span><b>{money(r.comm)}</b></div><div><span>Логистика</span><b>{money(Number(logistics)||0)}</b></div><div><span>Реклама</span><b>{money(Number(ads)||0)}</b></div><div><span>Налог</span><b>{money(r.t)}</b></div><div><span>Прочее</span><b>{money(Number(other)||0)}</b></div></div>
    <small className="calcHint">Формула: цена − себестоимость − комиссия − логистика − реклама − налог − прочие расходы.</small></section></div>
  </main>
}
