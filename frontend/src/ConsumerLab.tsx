import { useEffect, useState } from 'react'
import { request } from './api'
import type { PolicyEnvelope } from './api'
import { PolicyView } from './App'
import { useDashboardMode } from './DashboardMode'
import './consumerLab.css'

interface Trace {
 account_id:string;trace_id:string;source_version:string;consumer_id:string;actual_runtime_mode:string;policy_revision:string|null;policy_valid:boolean;
 baseline:{preview:unknown;field_paths:string[];schema_paths?:string[];byte_count:number};protected:{preview:unknown;field_paths:string[];schema_paths?:string[];byte_count:number};
 consumer_result:unknown;warnings:string[];decisions:{field:string;usage:string;sensitivity:string;action:string;evidence:string[];approved:boolean}[];
 log:unknown
}
interface State extends PolicyEnvelope {report:unknown}
export default function ConsumerLab(){
 const {mode}=useDashboardMode()
 const [accounts,setAccounts]=useState<{account_id:string}[]>([]),[account,setAccount]=useState(sessionStorage.getItem('veilmint-flow-account')||'')
 const [consumer,setConsumer]=useState('overview'),[runtime,setRuntime]=useState('ENFORCE')
 const [policy,setPolicy]=useState<State|null>(null),[rawTrace,setTrace]=useState<Trace|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const trace=rawTrace?.account_id===account&&rawTrace.consumer_id===consumer&&rawTrace.actual_runtime_mode===runtime?rawTrace:null
 const [matrix,setMatrix]=useState<Trace[]>([])
 const [review,setReview]=useState(false),[canary,setCanary]=useState<unknown>(null),[revision,setRevision]=useState(0)
 useEffect(()=>{void request<{accounts:{account_id:string}[]}>('/api/operator/accounts?limit=100').then(r=>setAccounts(r.accounts)).catch(()=>setError('Accounts unavailable.'))},[])
 useEffect(()=>{let active=true;setPolicy(null);setTrace(null);setCanary(null);setError('');void request<State>('/api/operator/consumer-lab/policies/'+consumer).then(r=>{if(active)setPolicy(r)}).catch(()=>{if(active)setError('Consumer policy unavailable.')});return()=>{active=false}},[consumer,revision])
 useEffect(()=>{setTrace(null);setCanary(null);setMatrix([])},[account,runtime])
 async function run(){setBusy(true);setError('');setTrace(null);try{setTrace(await request<Trace>('/api/operator/consumer-lab/run',{account_id:account,consumer,mode:runtime}))}catch{setError('Scenario unavailable. Attach the opt-in DEMO profile first, then inspect the consumer policy.')}finally{setBusy(false)}}
 async function seed(){setBusy(true);setError('');try{await request('/api/operator/consumer-lab/profiles/'+account,{});await run()}catch{setError('DEMO profile could not be attached.')}finally{setBusy(false)}}
 async function compare(){setBusy(true);setError('');try{const r=await request<{results:Trace[]}>('/api/operator/consumer-lab/matrix',{account_id:account,consumer,mode:runtime});setMatrix(r.results)}catch{setError('Matrix unavailable or producer changed. Retry after attaching a DEMO profile.')}finally{setBusy(false)}}
 async function verify(){setBusy(true);try{setCanary(await request('/api/operator/consumer-lab/verify',{account_id:account,consumer,mode:runtime}))}catch{setError('Canary execution unavailable.')}finally{setBusy(false)}}
 return <section className="flow-console">
  <div className="flow-boundary"><strong>OPERATOR-ONLY CONTROLLED SCENARIO</strong><span>Four in-process Python consumers · actual AST evidence · explicit review</span></div>
  <div className="flow-controls"><label>Producer account<select aria-label="Producer account" value={account} onChange={e=>{setAccount(e.target.value);sessionStorage.setItem('veilmint-flow-account',e.target.value)}}><option value="">Select a sandbox account</option>{accounts.map(a=><option key={a.account_id}>{a.account_id}</option>)}</select></label>
   <label>Authorized scenario consumer<select aria-label="Scenario consumer" value={consumer} onChange={e=>{setConsumer(e.target.value);setReview(false)}}>{['overview','payments','notifications','risk'].map(c=><option key={c}>{c}</option>)}</select></label>
   <label>Actual runtime mode<select aria-label="Actual runtime mode" value={runtime} onChange={e=>setRuntime(e.target.value)}>{['OBSERVE','WARN','ENFORCE'].map(m=><option key={m}>{m}</option>)}</select></label>
  </div>
  <div className="flow-actions"><button className="button secondary" disabled={!account||busy} onClick={()=>void seed()}>Attach fictional DEMO profile</button><button className="button primary" disabled={!account||busy||!policy} onClick={()=>void run()}>{busy?'Executing…':'Invoke consumer →'}</button><button className="button secondary" disabled={!account||busy} onClick={()=>void compare()}>Compare all consumers</button><button className="button secondary" onClick={()=>setReview(v=>!v)}>Consumer Policy Studio</button><button className="button secondary" disabled={!account||busy} onClick={()=>void verify()}>Run scoped canaries</button></div>
  <p className="flow-note">Attaching a profile persists clearly fictional enrichment only. It adds no funds or invented transactions. A pending policy keeps all fields; no removals are silently approved.</p>
  {error&&<div className="notice error" role="alert">{error}</div>}
  {review&&policy&&<PolicyView key={consumer+'-'+policy.policy?.revision.revision_id+'-'+policy.policy?.revision.status} endpoint={'/api/operator/consumer-lab/policies/'+consumer} envelope={policy} onChange={()=>{setRevision(v=>v+1);setTrace(null)}}/>}
  {canary!==null&&typeof canary==='object'&&'consumer_id' in canary&&canary.consumer_id===consumer&&<section className="panel trace-panel"><h2>Scoped canary execution</h2><pre>{JSON.stringify(canary,null,2)}</pre></section>}
  {!!matrix.length&&matrix.every(r=>r.account_id===account&&r.actual_runtime_mode===runtime)&&<section className="panel"><div className="panel-toolbar"><h2>Same producer · service comparison matrix</h2></div><div className="table-scroll"><table><thead><tr><th>Consumer</th><th>Policy</th><th>Mode</th><th>Valid approval</th><th>Emitted leaves</th><th>JSON bytes</th></tr></thead><tbody>{matrix.map(r=><tr key={r.consumer_id}><td>{r.consumer_id}</td><td>{r.policy_revision||'none'}</td><td>{r.actual_runtime_mode}</td><td>{r.policy_valid?'yes':'no — retained'}</td><td>{r.baseline.field_paths.length} → {r.protected.field_paths.length}</td><td>{r.baseline.byte_count} → {r.protected.byte_count}</td></tr>)}</tbody></table></div></section>}
  {!trace?<div className="empty-state"><h2>Select a producer and invoke a consumer</h2><p>The consumer receives the real runtime result from its separately reviewed policy. Approve eligible candidates in Consumer Policy Studio to demonstrate minimization.</p></div>:<>
   <div className="flow-lineage"><span>Canonical DEMO producer</span><b>→</b><span>VEILMINT · {trace.policy_revision||'No policy'}</span><b>→</b><span>{trace.consumer_id} handler</span></div>
   <div className={'notice '+(!trace.policy_valid?'error':'')}><p><strong>{trace.actual_runtime_mode} · {trace.policy_valid?'Approved policy at execution':'NO VALID APPROVAL — baseline retained'}</strong><br/>Trace {trace.trace_id}<br/>Source version <code>{trace.source_version}</code></p></div>
   <div className="flow-counts"><span>Leaf occurrences <strong>{trace.baseline.field_paths.length} → {trace.protected.field_paths.length}</strong><small>Unique paths {(trace.baseline.schema_paths||trace.baseline.field_paths).length} → {(trace.protected.schema_paths||trace.protected.field_paths).length}</small></span><span>UTF-8 JSON bytes <strong>{trace.baseline.byte_count} → {trace.protected.byte_count}</strong></span><span>Field reduction <strong>{((1-trace.protected.field_paths.length/trace.baseline.field_paths.length)*100).toFixed(1)}%</strong></span><span>Byte reduction <strong>{((1-trace.protected.byte_count/trace.baseline.byte_count)*100).toFixed(1)}%</strong></span></div>
   <section className="panel trace-panel"><h2>{mode==='standard'?'Standard / Baseline — before minimization':'VEILMINT / Protected — actual runtime output'}</h2><p>Both sides are frozen in this trace. Switching the global toggle only changes this view.</p><pre aria-label="Consumer comparison JSON">{JSON.stringify(mode==='standard'?trace.baseline.preview:trace.protected.preview,null,2)}</pre></section>
   <div className="two-column"><section className="panel trace-panel"><h2>Baseline producer JSON</h2><pre>{JSON.stringify(trace.baseline.preview,null,2)}</pre></section><section className="panel trace-panel"><h2>Consumer-delivered JSON</h2><pre>{JSON.stringify(trace.protected.preview,null,2)}</pre></section></div>
   <section className="panel"><div className="panel-toolbar"><h2>Field lineage & decision diff</h2><span>Unique top-level policy fields; nested emitted leaves counted above</span></div><div className="table-scroll"><table><thead><tr><th>Field</th><th>Consumer usage</th><th>Sensitivity</th><th>Actual API decision</th><th>Evidence</th></tr></thead><tbody>{trace.decisions.map(d=><tr key={d.field}><td><code>{d.field}</code></td><td>{d.usage}</td><td>{d.sensitivity}</td><td>{d.action}{d.approved?' · reviewed':''}</td><td><details><summary>Source evidence</summary>{d.evidence.map(e=><p key={e}>{e}</p>)}</details></td></tr>)}</tbody></table></div></section>
   <div className="two-column"><section className="panel trace-panel"><h2>Actual consumer function result</h2><pre>{JSON.stringify(trace.consumer_result,null,2)}</pre></section><section className="panel trace-panel"><h2>Persisted sanitized metadata · same correlation</h2><pre>{JSON.stringify(trace.log,null,2)}</pre></section></div>
   {!!trace.warnings.length&&<div className="notice error"><p>{trace.warnings.join(' ')}</p></div>}
  </>}
 </section>
}
