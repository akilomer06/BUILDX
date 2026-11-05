import { useEffect, useState } from 'react'
import { request } from './api'
import { money } from './bank/money'
import { RequestEvidence } from './RequestEvidence'
import type { BankEvent } from './RequestEvidence'
interface AccountRow {account_id:string;customer_id:string;display_name:string;username:string;currency:string;status:string;masked_account_reference:string;available_balance_minor:number|string}
interface Detail {
  customer:Record<string,unknown>;source_record:Record<string,unknown>;source_field_paths:string[];
  contract_excluded_paths:string[];customer_dto:Record<string,unknown>;
  current_policy_preview:{output:Record<string,unknown>;trace:{policy_valid:boolean;policy_revision:string|null;removed_paths:string[];warnings:string[]};label:string};
  ledger:Record<string,unknown>[];beneficiaries:Record<string,unknown>[];transfers:Record<string,unknown>[];
  events:BankEvent[];demo_profile_present:boolean
}
export default function AccountsExplorer({inspection=false}:{inspection?:boolean}){
  const [search,setSearch]=useState(''),[offset,setOffset]=useState(0)
  const [list,setList]=useState<{accounts:AccountRow[];total:number}|null>(null)
  const [account,setAccount]=useState(''),[detail,setDetail]=useState<Detail|null>(null)
  const [reveal,setReveal]=useState(false),[error,setError]=useState(''),[reload,setReload]=useState(0)
  const [eventId,setEventId]=useState<number|null>(null)
  const hide=()=>{setReveal(false);setDetail(null);setList(null)}
  useEffect(()=>{if(!reveal)return;const timer=setTimeout(hide,45000);return()=>clearTimeout(timer)},[reveal])
  useEffect(()=>{let active=true;setList(null);setError('');const timer=setTimeout(()=>{void request<{accounts:AccountRow[];total:number}>(`/api/operator/accounts?search=${encodeURIComponent(search)}&offset=${offset}&reveal=${reveal}`).then(r=>{if(active)setList(r)}).catch(()=>{if(active)setError('Accounts could not be loaded. Check backend availability.')})},200);return()=>{active=false;clearTimeout(timer)}},[search,offset,reveal,reload])
  useEffect(()=>{if(!account)return;let active=true;setDetail(null);setEventId(null);setError('');void request<Detail>(`/api/operator/accounts/${encodeURIComponent(account)}?reveal=${reveal}`).then(r=>{if(active){setDetail(r);if(inspection&&r.events.length)setEventId(r.events[0].id)}}).catch(()=>{if(active)setError('Account details could not be loaded.')});return()=>{active=false}},[account,reveal,reload,inspection])
  const select=(id:string)=>{setReveal(false);setDetail(null);setAccount(id);setEventId(null)}
  return <section>
    <div className="notice"><p><strong>{inspection?'Real bank protection inspection.':'Read-only sandbox Accounts Explorer.'}</strong> Sensitive values are masked by default. Credentials and credential hashes are never selected. Revealing data is local to this view for 45 seconds.</p></div>
    <div className="explorer-toolbar"><label className="search">Search account ID, customer name or username<input aria-label="Search bank accounts" maxLength={120} value={search} onChange={e=>{setSearch(e.target.value);setOffset(0)}}/></label><div className="button-row"><button className="button secondary" onClick={()=>setReload(v=>v+1)}>Refresh accounts</button><label className="reveal-control"><input type="checkbox" checked={reveal} onChange={e=>{setDetail(null);setList(null);setReveal(e.target.checked)}}/> Reveal sandbox fields for 45 seconds</label></div></div>
    {reveal&&<div className="notice error" role="status">Sensitive sandbox values are visible temporarily. Hiding the view does not erase anything you manually copy.</div>}
    {error&&<div className="notice error" role="alert">{error}</div>}
    <section className="panel"><div className="panel-toolbar"><h2>Accounts {list&&`· ${list.total}`}</h2><span className="badge">READ ONLY</span></div>
    {!list?<p className="no-results" role="status">Loading bank records…</p>:!list.accounts.length?<div className="empty-state"><h3>No matching accounts</h3><p>Register a customer in NEXUS BANK, or change the search. No accounts or balances are invented here.</p></div>:<div className="table-scroll"><table><thead><tr><th>Account ID</th><th>Customer</th><th>Reference</th><th>Balance (INR)</th><th>Status</th></tr></thead><tbody>{list.accounts.map(row=><tr key={row.account_id}><td><button className="text-button" onClick={()=>select(row.account_id)}>{row.account_id}</button></td><td>{row.display_name}<small className="muted" style={{display:'block'}}>{row.username}</small></td><td>{row.masked_account_reference}</td><td>{typeof row.available_balance_minor==='number'?money(row.available_balance_minor,row.currency):row.available_balance_minor}</td><td>{row.status}</td></tr>)}</tbody></table></div>}
    <div className="table-footer"><button className="text-button" disabled={offset===0} onClick={()=>setOffset(v=>Math.max(0,v-25))}>Previous</button><span>{offset+1}–{offset+(list?.accounts.length||0)}</span><button className="text-button" disabled={!list||offset+25>=list.total} onClick={()=>setOffset(v=>v+25)}>Next</button></div></section>
    {!account?<div className="empty-state"><h3>Select an account</h3><p>Inspect its source fields, contract boundary, current policy preview and actual request evidence.</p></div>:!detail?<p role="status">Loading selected account…</p>:<>
      <section className="panel trace-panel"><span className="eyebrow">{account}</span><h2 style={{margin:'12px 0'}}>Source record → response contract → policy preview</h2><p>{detail.current_policy_preview.label}</p><div className="two-column"><div><h3>Selected bank source fields</h3><pre aria-label="Bank source record">{JSON.stringify(detail.source_record,null,2)}</pre></div><div><h3>Current protected response preview</h3><pre aria-label="Bank response preview">{JSON.stringify(detail.current_policy_preview.output,null,2)}</pre></div></div><div className="trace-grid"><div><span>Excluded by response contract</span><code>{detail.contract_excluded_paths.join(', ')||'None'}</code></div><div><span>Approved policy removals</span><code>{detail.current_policy_preview.trace.removed_paths.join(', ')||'None'}</code></div></div><p>Policy {detail.current_policy_preview.trace.policy_revision||'unavailable'} · {detail.current_policy_preview.trace.policy_valid?'Valid current approval':'Fail-safe: DTO retained'}</p>
      {!detail.demo_profile_present&&<div className="notice"><p>Optional fictional contact fields are not loaded. To add clearly generated examples, the host operator can run:<br/><code>docker compose exec backend python -m veilmint bank demo-profile --account {account} --synthetic-only</code><br/>Then refresh this account in the customer app to create real masking evidence.</p></div>}</section>
      {!inspection&&<div className="two-column"><section className="panel trace-panel"><h2>Customer record · selected safe columns</h2><pre>{JSON.stringify(detail.customer,null,2)}</pre></section><section className="panel trace-panel"><h2>Ledger · latest 25 entries</h2><pre>{JSON.stringify(detail.ledger,null,2)}</pre></section><section className="panel trace-panel"><h2>Beneficiaries · latest 25</h2><pre>{JSON.stringify(detail.beneficiaries,null,2)}</pre></section><section className="panel trace-panel"><h2>Transfers · latest 25</h2><pre>{JSON.stringify(detail.transfers,null,2)}</pre></section></div>}
      <section className="panel trace-panel"><h2>Actual account request evidence</h2>{detail.events.length?<div className="request-links">{detail.events.map(e=><button key={e.id} className="button secondary" onClick={()=>setEventId(e.id)}>{new Date(e.created_at).toLocaleString()} · {e.correlation_id}</button>)}</div>:<p className="no-results">No linked customer request has been recorded yet. Refresh the account from the customer app, then refresh here. Opening this explorer creates no bank traffic.</p>}</section>
      {eventId!==null&&<RequestEvidence eventId={eventId}/>}
    </>}
  </section>
}
