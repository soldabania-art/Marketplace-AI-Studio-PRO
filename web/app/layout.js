import './globals.css'
import './workspace.css'
import './site-foundation.css'
import './fbo.css'
import CookieConsent from './components/CookieConsent'

export const metadata = {
  title: 'Marketplace AI Studio Cloud',
  description: 'AI operating system for Wildberries and Ozon sellers'
}

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>{children}<CookieConsent /></body>
    </html>
  )
}
