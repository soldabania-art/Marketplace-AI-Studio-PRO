import { Suspense } from 'react'
import CardFactoryWorkspace from '../../components/CardFactoryWorkspace'

export default function Page(){
  return <Suspense fallback={<main className="workPage"><div className="workPanel">Загружаем AI Card Factory…</div></main>}><CardFactoryWorkspace/></Suspense>
}
