import { useEffect, useState } from 'react'
import { request } from './api'
import ResponseInspector from './ResponseInspector'
export type TrafficEvent={account_id?:string|null;id:number;created_at:string;correlation_id:string;endpoint:string;method:string;http_status:number;destination:string;policy_revision:string|null;mode:string;outcome:string;kept_paths:string[];removed_paths:string[];warnings:string[];log_outcome:string;log_record_id:number;latency_ms:number;log_actions:{path:(string|number)[];action:string}[]}
export default function LiveTraffic(){
  const [events,setEvents]=useState<TrafficEvent[]>([])
  const [error,setError]=useState('')
  const [selected,setSelected]=useState<TrafficEvent|null>(null)
  const [filter,setFilter]=useState('')
  const [loaded,setLoaded]=useState(false)
  useEffect(()=>{let alive=true;let timer:ReturnType<typeof setTimeout>
    async function poll(){try{const result=await request<{events:TrafficEvent[]}>('/api/traffic');if(alive){setEvents(result.events);setError('');setLoaded(true)}}catch{if(alive){setError('Traffic connection unavailable. Showing the last received records; no activity is assumed.');setLoaded(true)}}finally{if(alive)timer=setTimeout(()=>void poll(),3000)}}
    void poll();return()=>{alive=false;clearTimeout(timer)}
  },[])
  const rows=events.filter(e=>(e.correlation_id+' '+e.endpoint).includes(filter))
  return <section><div className="notice"><p><strong>Actual NEXUS BANK requests.</strong> Polling every 3 seconds. Up to 100 recent records shown; 1,000 retained. Click a request to inspect its captured JSON. Standard shows the captured response; VEILMINT masks it on the server.</p><a href="/bank/" className="text-button">Open customer app ↗</a></div>{error&&<div role="alert" className="notice error">{error}</div>}<label className="search">Find correlation ID or endpoint<input aria-label="Filter real traffic" value={filter} onChange={e=>setFilter(e.target.value)}/></label><section className="panel"><div className="panel-toolbar"><h2>Live traffic · {events.length} received records</h2><span className="muted">{loaded?'Actual persisted requests':'Connecting…'}</span></div>{!events.length?<div className="empty-state"><h3>{loaded?'No bank traffic yet':'Loading actual traffic…'}</h3><p>Register or sign in through NEXUS BANK, then view an account or make a sandbox transfer.</p></div>:<div className="table-scroll"><table><thead><tr><th>Received</th><th>Request</th><th>Status</th><th>Policy / mode</th><th>Log protection</th><th>Measured latency</th></tr></thead><tbody>{rows.map(e=><tr key={e.id}><td>{new Date(e.created_at).toLocaleTimeString()}</td><td><button className="text-button" aria-haspopup="dialog" aria-expanded={selected?.id===e.id} aria-controls={selected?.id===e.id?"selected-api-response":undefined} onClick={()=>setSelected(current=>current?.id===e.id?null:e)}>{e.method} {e.endpoint}</button><code style={{display:'block',fontSize:9,marginTop:6}}>{e.correlation_id}</code></td><td>{e.http_status} · {e.outcome}</td><td><code>{e.policy_revision||'No response policy'}</code><br/>{e.mode}</td><td>{e.log_outcome}</td><td>{e.latency_ms} ms</td></tr>)}</tbody></table></div>}</section>{selected&&<ResponseInspector key={selected.correlation_id} event={selected} onClose={()=>setSelected(null)}/>}</section>
}
