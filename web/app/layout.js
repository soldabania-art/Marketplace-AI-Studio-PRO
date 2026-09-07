import './globals.css'
import './workspace.css'
import './site-foundation.css'
import './fbo.css'
import './store-selector.css'
import CookieConsent from './components/CookieConsent'
import GlobalStoreSelector from './components/GlobalStoreSelector'

export const metadata = {
  title: 'Marketplace AI Studio Cloud',
  description: 'AI operating system for marketplace sellers'
}

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body><GlobalStoreSelector />{children}<CookieConsent /></body>
    </html>
  )
}
