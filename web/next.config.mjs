/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  poweredByHeader: false,
  async headers(){
    const securityHeaders=[
      {key:'Content-Security-Policy',value:"default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self'; manifest-src 'self'; worker-src 'self' blob:"},
      {key:'Strict-Transport-Security',value:'max-age=63072000; includeSubDomains; preload'},
      {key:'X-Content-Type-Options',value:'nosniff'},
      {key:'X-Frame-Options',value:'DENY'},
      {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},
      {key:'Permissions-Policy',value:'camera=(self), microphone=(), geolocation=(), payment=()'},
      {key:'Cross-Origin-Opener-Policy',value:'same-origin'},
      {key:'X-DNS-Prefetch-Control',value:'off'},
    ]
    return [
      {source:'/:path*',headers:securityHeaders},
      {source:'/api/:path*',headers:[{key:'Cache-Control',value:'no-store, max-age=0'},{key:'Pragma',value:'no-cache'}]},
    ]
  },
}

export default nextConfig
