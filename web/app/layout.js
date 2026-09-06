import './globals.css'

export const metadata = {
  title: 'Marketplace AI Studio Cloud',
  description: 'AI operating system for Wildberries and Ozon sellers'
}

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  )
}
