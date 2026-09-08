import './globals.css'
import './brand.css'
import './workspace.css'
import './card-factory.css'
import './start.css'
import './site-foundation.css'
import './fbo.css'
import './store-selector.css'
import CookieConsent from './components/CookieConsent'
import GlobalStoreSelector from './components/GlobalStoreSelector'

export const metadata = {
  metadataBase: new URL('https://trovendi.ru'),
  title: { default: 'TROVENDI — AI Commerce OS', template: '%s · TROVENDI' },
  description: 'AI-платформа для запуска и управления продажами на маркетплейсах',
  applicationName: 'TROVENDI',
  icons: { icon: '/icon.svg' },
  openGraph: {
    title: 'TROVENDI — AI Commerce OS',
    description: 'От одной фотографии товара до ежедневного управления магазином с AI.',
    url: 'https://trovendi.ru',
    siteName: 'TROVENDI',
    locale: 'ru_RU',
    type: 'website',
  },
}

export const viewport = { themeColor: '#0b1728' }

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body><GlobalStoreSelector />{children}<CookieConsent /></body>
    </html>
  )
}
