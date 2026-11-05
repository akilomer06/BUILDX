import { useEffect,useState } from 'react'
declare const __VERCEL_HOSTED__:boolean
export default function CloudHostStatus(){
 const enabled=typeof __VERCEL_HOSTED__!=='undefined'&&__VERCEL_HOSTED__
 const [status,setStatus]=useState<{backendConfigured:boolean;operatorAccessConfigured:boolean}|null>(null)
 useEffect(()=>{if(!enabled)return;let active=true;void fetch('/api/deployment-status').then(r=>r.json()).then(s=>{if(active)setStatus(s)}).catch(()=>{});return()=>{active=false}},[enabled])
 if(!enabled)return null
 return <div className="notice"><p><strong>Hosted VEILMINT frontend.</strong> {status?.backendConfigured?'Persistent backend URL is configured.':'Persistent backend hosting is not connected yet; bank actions and saved records are unavailable until setup is finished.'} {status?.operatorAccessConfigured?'Operator APIs require operator sign-in.':'Operator access is closed until cloud credentials are configured.'}</p>{status?.operatorAccessConfigured&&<a className="button secondary" href="/api/cloud-login">Operator sign-in</a>}</div>
}
