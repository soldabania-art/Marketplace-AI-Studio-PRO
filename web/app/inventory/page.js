import Link from 'next/link'
import StudioSection from '../../components/StudioSection'

export default function Page(){
  return <><StudioSection eyebrow="СКЛАД" title="Остатки" description="Контроль дефицита, излишков и прогноз пополнения по товарам." primary="Проверить остатки" cards={[{title:'Дефицит',text:'Товары с риском закончиться раньше срока.',action:'Найти дефицит'},{title:'Излишки',text:'Замороженные деньги и медленно продающиеся остатки.',action:'Найти излишки'},{title:'Пополнение',text:'Расчёт приоритетов поставки по продажам и запасу.',action:'Рассчитать поставку'}]}/><div style={{position:'fixed',right:24,bottom:24,zIndex:20}}><Link href="/fbo-slots" className="primaryBtn">Найти склады FBO / FBW</Link></div></>
}
