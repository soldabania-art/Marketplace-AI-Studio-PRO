export function BrandMark({size=38,className=''}) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="TROVENDI">
      <defs>
        <linearGradient id="trovendi-mark-gradient" x1="10" y1="54" x2="54" y2="10" gradientUnits="userSpaceOnUse">
          <stop stopColor="#42E7A4"/>
          <stop offset=".52" stopColor="#5BA8FF"/>
          <stop offset="1" stopColor="#9F7AEA"/>
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="17" fill="#0B1728"/>
      <rect x="2.75" y="2.75" width="58.5" height="58.5" rx="16.25" fill="none" stroke="url(#trovendi-mark-gradient)" strokeOpacity=".55" strokeWidth="1.5"/>
      <path d="M15 17.5H49" fill="none" stroke="url(#trovendi-mark-gradient)" strokeWidth="8" strokeLinecap="round"/>
      <path d="M32 49V25M23.5 33.5 32 25l8.5 8.5" fill="none" stroke="url(#trovendi-mark-gradient)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

export default function BrandLogo({className='',subtitle='AI Commerce OS'}) {
  return (
    <div className={`brand ${className}`.trim()} aria-label="TROVENDI">
      <BrandMark className="brandMarkSvg"/>
      <div className="brandWords"><strong>TROVENDI</strong><span>{subtitle}</span></div>
    </div>
  )
}
