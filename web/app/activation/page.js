'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, LockKeyhole } from 'lucide-react'
import BrandLogo from '../../components/BrandLogo'

const labels={verify_email:'Подтверждение email',checkout:'Оплата тарифа',setup_mfa:'Настройка MFA',verify_mfa:'Подтверждение входа',connect_store:'Подключение магазина',ready:'Готово'}

export default function ActivationPage(){
  const router=useRouter();const [state,setState]=useState({loading:true,error:'',step:null});const [workspaces,setWorkspaces]=useState([])
  useEffect(()=>{let active=true;const selected=new URLSearchParams(window.location.search).get('workspace_id');const activate=id=>fetch(`/api/billing/activation${id?`?workspace_id=${encodeURIComponent(id)}`:''}`,{cache:'no-store'}).then(async response=>{const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось продолжить активацию');if(!active)return;setState({loading:false,error:'',step:payload});if(payload.ready&&payload.href)setTimeout(()=>router.replace(payload.href),700)}).catch(error=>active&&setState({loading:false,error:error.message,step:null}));if(selected){activate(selected);return()=>{active=false}}fetch('/api/stores',{cache:'no-store'}).then(async response=>{const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось загрузить рабочие пространства');if(!active)return;const rows=payload.workspaces||[];if(rows.length>1){setWorkspaces(rows);setState({loading:false,error:'',step:null})}else activate(rows[0]?.id)}).catch(error=>active&&setState({loading:false,error:error.message,step:null}));return()=>{active=false}},[router])
  const choosing=workspaces.length>1&&!state.loading&&!state.step&&!state.error
  return <main className="sectionPage"><div className="sectionTop"><Link href="/"><BrandLogo/></Link><span className="sectionNotice"><LockKeyhole size={16}/> Сервер проверяет каждый этап</span></div><section className="sectionHero"><span className="eyebrow">АКТИВАЦИЯ TROVENDI</span><h1>{choosing?'Выберите рабочее пространство':state.loading?'Определяем безопасный следующий шаг…':state.error?'Не удалось продолжить':labels[state.step?.stage]||'Следующий шаг'}</h1><p>{choosing?'Тариф и активация применяются только к выбранному рабочему пространству.':state.error||state.step?.message||'Проверяем аккаунт, оплату, MFA и подключение магазина.'}</p>{choosing&&workspaces.map(workspace=><Link className="primaryBtn" key={workspace.id} href={`/activation?workspace_id=${encodeURIComponent(workspace.id)}`}>{workspace.name} <ArrowRight size={17}/></Link>)}{state.step?.href&&!state.step.ready&&<Link className="primaryBtn" href={state.step.href}>Продолжить <ArrowRight size={17}/></Link>}{state.step?.ready&&<div className="sectionNotice"><CheckCircle2 size={17}/> Открываем выбранное рабочее пространство…</div>}{state.error&&<button className="primaryBtn" onClick={()=>window.location.reload()}>Повторить проверку</button>}</section></main>
}
