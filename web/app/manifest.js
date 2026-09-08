export default function manifest() {
  return {
    name: 'TROVENDI — AI Commerce OS',
    short_name: 'TROVENDI',
    description: 'AI-платформа для запуска и управления продажами на маркетплейсах',
    start_url: '/',
    display: 'standalone',
    background_color: '#07111f',
    theme_color: '#0b1728',
    lang: 'ru',
    icons: [{src:'/trovendi-mark.svg',sizes:'any',type:'image/svg+xml',purpose:'any'}],
  }
}
