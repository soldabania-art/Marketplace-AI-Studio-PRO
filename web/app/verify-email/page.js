import { Suspense } from 'react'
import EmailConfirmation from './EmailConfirmation'

export const metadata = {
  title: 'Подтверждение email',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
}

export default function VerifyEmailPage() {
  return <main className="authShell simpleAuth"><Suspense fallback={<p role="status">Загружаем подтверждение…</p>}><EmailConfirmation /></Suspense></main>
}
