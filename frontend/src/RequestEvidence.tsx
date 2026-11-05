import { useEffect, useState } from 'react'
import { request } from './api'
export interface BankEvent {
  id:number;created_at:string;correlation_id:string;endpoint:string;method:string;http_status:number;
  destination:string;policy_revision:string|null;mode:string;outcome:string;kept_paths:string[];removed_paths:string[];
  warnings:string[];log_outcome:string;log_record_id:number;latency_ms:number;account_id?:string|null;
  source_field_paths?:string[];contract_excluded_paths?:string[];policy_valid?:boolean|null;
  header_actions?:{direction:string;name:string;present:boolean;action:string;reason:string}[];
  log_actions:{path:(string|number)[];action:string}[]
}
export function RequestEvidence({eventId}:{eventId:number}){
  const [result,setResult]=useState<{event:BankEvent;persisted:{id:number;event:Record<string,unknown>;policy_revision:string|null}}|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{let active=true;setResult(null);setError('');void request<typeof result>(`/api/operator/events/${eventId}`).then(r=>{if(active)setResult(r)}).catch(()=>{if(active)setError('Persisted request evidence could not be loaded. No result has been assumed.')});return()=>{active=false}},[eventId])
  if(error)return <div className="notice error" role="alert">{error}</div>
  if(!result)return <p role="status">Reading the actual protected log record…</p>
  const e=result.event
  return <section className="panel trace-panel" aria-label="Real request detail">
    <span className="eyebrow">ACTUAL CUSTOMER REQUEST · PERSISTED EVIDENCE</span>
    <h2 style={{margin:'12px 0'}}>{e.method} {e.endpoint}</h2>
    <p className="mono">{e.correlation_id}</p><p>Policy {e.policy_revision||'unavailable'} · {e.mode} · {e.policy_valid===true?'Valid approved response policy':e.policy_valid===false?'Fail-safe response retained':'No response policy on this route'}</p>
    <div className="table-scroll"><table><thead><tr><th>Source field</th><th>Customer response decision</th><th>Log decision</th></tr></thead><tbody>{(e.source_field_paths||e.kept_paths).map(path=>{
      const excluded=e.contract_excluded_paths?.includes(path)
      const log=e.log_actions.find(a=>'/'+a.path.join('/')===path)
      return <tr key={path}><td><code>{path}</code></td><td>{excluded?'EXCLUDED BY RESPONSE CONTRACT':e.removed_paths.includes(path)?'REMOVE · approved VEILMINT policy':'KEEP'}</td><td>{log?.action||'Not collected as a log value'}</td></tr>
    })}</tbody></table></div>
    <div className="notice"><p>Contract exclusions happen before the API minimizer. Only approved policy removals count as VEILMINT REMOVE. The values of credentials and authentication headers are never copied into log input.</p></div>
    <h3>Header protection at log collection</h3>
    {e.header_actions?.length?<div className="table-scroll"><table><thead><tr><th>Direction</th><th>Header name</th><th>Observed</th><th>Log decision</th></tr></thead><tbody>{e.header_actions.map(h=><tr key={h.direction+h.name}><td>{h.direction}</td><td><code>{h.name}</code></td><td>{h.present?'Present; authentication transport preserved':'Not present'}</td><td>{h.present?h.action:'No value collected'}</td></tr>)}</tbody></table></div>:<p>This older record predates header-presence evidence. Refresh the customer account to create a new record.</p>}
    <h3 style={{marginTop:24}}>Actions applied before log persistence</h3><div className="action-grid">{e.log_actions.map((a,i)=><div className="action-row" key={i}><code>/{a.path.join('/')}</code><span className="badge">{a.action}</span></div>)}</div>
    <h3>Actual persisted sanitized log #{result.persisted.id}</h3><pre aria-label="Persisted sanitized bank log">{JSON.stringify(result.persisted.event,null,2)}</pre>
    <p className="muted">Read back from SQLite and matched to this correlation ID. No original event, password, token or header value is available here.</p>
    {!!e.warnings.length&&<div className="notice"><p>{e.warnings.join(' ')}</p></div>}
  </section>
}
