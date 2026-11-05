import { createHash, timingSafeEqual } from 'node:crypto'

const digest=value=>createHash('sha256').update(value).digest()
function operatorAuthorized(header){
  if(!process.env.CLOUD_OPERATOR_PASSWORD||process.env.CLOUD_OPERATOR_PASSWORD.length<16)return false
  if(typeof header!=='string'||!header.startsWith('Basic '))return false
  const value=Buffer.from(header.slice(6),'base64').toString('utf8')
  const separator=value.indexOf(':')
  return separator>=0&&timingSafeEqual(digest(value.slice(0,separator)),digest(process.env.CLOUD_OPERATOR_USERNAME||'operator'))&&
    timingSafeEqual(digest(value.slice(separator+1)),digest(process.env.CLOUD_OPERATOR_PASSWORD))
}
export function upstreamPath(raw){
  const segments=String(raw||'').split('/').map(decodeURIComponent)
  if(segments.some(part=>!part||part==='.'||part==='..'||!/^[A-Za-z0-9_-]+$/.test(part)))throw new Error('Invalid route')
  return '/api/'+segments.join('/')
}
export default async function handler(req,res){
  res.setHeader('Cache-Control','no-store')
  res.setHeader('X-Content-Type-Options','nosniff')
  const fail=(status,detail)=>res.status(status).json({detail})
  let path
  try{path=upstreamPath(req.query.forwardPath)}catch{return fail(400,'Invalid API route.')}
  if(path==='/api/deployment-status')return res.status(200).json({backendConfigured:Boolean(process.env.BACKEND_URL),operatorAccessConfigured:Boolean(process.env.CLOUD_OPERATOR_PASSWORD&&process.env.VEILMINT_OPERATOR_TOKEN)})
  const origin=req.headers.origin
  if(origin&&origin!=='https://'+req.headers.host)return fail(403,'Request origin rejected.')
  const bank=path.startsWith('/api/bank/')
  if(!bank&&!operatorAuthorized(req.headers.authorization)){
    res.setHeader('WWW-Authenticate','Basic realm="VEILMINT operator", charset="UTF-8"')
    return fail(401,'Operator sign-in required. Open /api/cloud-login to sign in.')
  }
  if(path==='/api/cloud-login'){res.setHeader('Location','/');return res.status(302).end()}
  if(!process.env.BACKEND_URL)return fail(503,'Persistent backend hosting is not connected yet. See deployment status.')
  let base
  try{
    base=new URL(process.env.BACKEND_URL)
    if(base.protocol!=='https:'||base.username||base.password||base.pathname!=='/'||base.search||base.hash)throw new Error()
  }catch{return fail(503,'Backend URL configuration is invalid.')}
  if(!bank&&!process.env.VEILMINT_OPERATOR_TOKEN)return fail(503,'Operator backend access is not configured.')
  if(['CONNECT','TRACE'].includes(req.method))return fail(405,'Method not allowed.')
  const headers={Accept:'application/json'}
  for(const name of ['content-type','cookie','x-nexus-request'])if(req.headers[name])headers[name]=req.headers[name]
  if(origin)headers.Origin=base.origin
  if(!bank)headers['X-VEILMINT-Operator']=process.env.VEILMINT_OPERATOR_TOKEN
  const target=new URL(path,base)
  const incoming=new URL(req.url,'https://'+req.headers.host)
  for(const [key,value] of incoming.searchParams)if(key!=='forwardPath')target.searchParams.append(key,value)
  let body
  if(!['GET','HEAD'].includes(req.method)){
    if(req.body!==undefined)body=typeof req.body==='string'||Buffer.isBuffer(req.body)?req.body:JSON.stringify(req.body)
    else{const chunks=[];let size=0;for await(const chunk of req){size+=Buffer.byteLength(chunk);if(size>65536)return fail(413,'Request body too large.');chunks.push(Buffer.from(chunk))}body=Buffer.concat(chunks)}
    if(Buffer.byteLength(body||'')>65536)return fail(413,'Request body too large.')
  }
  try{
    const response=await fetch(target,{method:req.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(25000)})
    for(const [name,value] of response.headers){
      if(['content-type','x-request-id','x-nexus-log-protection'].includes(name)||name.startsWith('x-captured-')||name.startsWith('x-privacy-'))res.setHeader(name,value)
    }
    const cookies=response.headers.getSetCookie()
    if(cookies.length)res.setHeader('Set-Cookie',cookies)
    return res.status(response.status).send(Buffer.from(await response.arrayBuffer()))
  }catch{return fail(503,'Backend connection unavailable. Retry transfers with the same idempotency key.')}
}
