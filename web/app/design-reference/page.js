import { Suspense } from 'react'
import D01DesignReference from '../../components/D01DesignReference'
import './d01.css'

export const metadata = {
  title: 'D01 · Визуальный эталон',
  description: 'Демонстрационный визуальный прототип TROVENDI на синтетических данных.',
  robots: { index: false, follow: false },
}

function LoadingFrame() {
  return <main className="d01 d01-ledger"><div className="d01-boot">Собираем визуальный эталон…</div></main>
}

export default function DesignReferencePage() {
  return <Suspense fallback={<LoadingFrame />}><D01DesignReference /></Suspense>
}
