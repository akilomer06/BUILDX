import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { money, parseMinor } from './money'
import './bank.css'

type Profile = {customer_id:string;display_name:string}
type Entry = {id:string;amount_minor:number;currency:string;reference:string;kind:string;created_at:string;status:string}
type Account = {account_id:string;display_name:string;account_type:string;currency:string;status:string;masked_account_reference:string;available_balance_minor:number;recent_transactions:Entry[]}
type Beneficiary = {id:string;destination_account_id:string;label:string}
type Receipt = {id:string;reference:string;amount_minor:number;currency:string;status:string}
type Page = 'overview'|'account'|'transactions'|'beneficiaries'|'transfer'

export default function BankApp(){
  const [profile,setProfile]=useState<Profile|null>(null)
  const [account,setAccount]=useState<Account|null>(null)
  const [accounts,setAccounts]=useState<{account_id:string;masked_account_reference:string}[]>([])
  const [entries,setEntries]=useState<Entry[]>([])
  const [offset,setOffset]=useState(0)
  const [beneficiaries,setBeneficiaries]=useState<Beneficiary[]>([])
  const [page,setPage]=useState<Page>('overview')
  const [busy,setBusy]=useState(false)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [register,setRegister]=useState(false)
  const [username,setUsername]=useState('')
  const [password,setPassword]=useState('')
  const [name,setName]=useState('')
  const [destination,setDestination]=useState('')
  const [label,setLabel]=useState('')
  const [amount,setAmount]=useState('')
  const [review,setReview]=useState<{amount_minor:number;destination_account_id:string;source_account_id:string;idempotency_key:string}|null>(null)
  const [receipt,setReceipt]=useState<Receipt|null>(null)
  const [correlation,setCorrelation]=useState('')
  const clearSession=()=>{setRegister(false);setName('');setUsername('');setProfile(null);setAccount(null);setEntries([]);setBeneficiaries([]);setAccounts([]);setReview(null);setReceipt(null);setDestination('');setAmount('')}
  async function api<T>(path:string,body?:unknown):Promise<T>{
    let r:Response
    try{r=await fetch('/api/bank'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Nexus-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)})}
    catch{throw new Error('The bank is unreachable. Check your connection. Retry a transfer without changing its reviewed details.')}
    const id=r.headers.get('X-Request-ID');if(id)setCorrelation(id)
    if(r.status===401){clearSession();throw new Error('Session expired or sign-in details are invalid. Please sign in.')}
    if(!r.ok){const result=await r.json().catch(()=>({}));throw new Error(typeof result.detail==='string'?result.detail:'Please check the form and try again.')}
    return r.json() as Promise<T>
  }
  async function loadAccount(id:string){
    const [detail,transactions,saved]=await Promise.all([api<Account>('/accounts/'+id),api<Entry[]>('/accounts/'+id+'/transactions?limit=20&offset=0'),api<Beneficiary[]>('/beneficiaries')])
    setAccount(detail);setEntries(transactions);setBeneficiaries(saved);setOffset(0)
  }
  async function reload(){
    const me=await api<Profile>('/customers/me');setProfile(me)
    const list=await api<{account_id:string;masked_account_reference:string}[]>('/accounts');setAccounts(list)
    if(list.length)await loadAccount(list[0].account_id)
  }
  useEffect(()=>{void reload().catch(()=>{}).finally(()=>setLoading(false))},[])
  async function authenticate(e:FormEvent){e.preventDefault();setBusy(true);setError('');setNotice('')
    try{if(register)await api('/auth/register',{display_name:name,username,password});await api('/auth/login',{username,password});await reload();setPage('overview')}
    catch(reason){setError((reason as Error).message)}finally{setPassword('');setBusy(false)}
  }
  async function logout(){setBusy(true);setError('');try{await api('/auth/logout',{});clearSession()}catch(r){setError((r as Error).message)}finally{setBusy(false)}}
  async function addBeneficiary(e:FormEvent){e.preventDefault();setBusy(true);setError('');setNotice('')
    try{await api('/beneficiaries',{destination_account_id:destination.trim(),label});setBeneficiaries(await api<Beneficiary[]>('/beneficiaries'));setNotice('Beneficiary saved.');setDestination('');setLabel('')}
    catch(r){setError((r as Error).message)}finally{setBusy(false)}
  }
  function prepare(e:FormEvent){e.preventDefault();setError('');setReceipt(null)
    try{if(!account)throw new Error('Select your source account.');setReview({amount_minor:parseMinor(amount),destination_account_id:destination.trim(),source_account_id:account.account_id,idempotency_key:'nexus-'+Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('')})}
    catch(r){setError((r as Error).message)}
  }
  async function confirm(){if(!review)return;setBusy(true);setError('')
    try{const result=await api<Receipt>('/transfers',{...review,currency:'INR'});setReceipt(result);setReview(null);setAmount('');if(account)await loadAccount(account.account_id)}
    catch(r){setError((r as Error).message)}finally{setBusy(false)}
  }
  async function paginate(next:number){if(!account)return;setBusy(true);setError('');try{setEntries(await api<Entry[]>(`/accounts/${account.account_id}/transactions?limit=20&offset=${next}`));setOffset(next)}catch(r){setError((r as Error).message)}finally{setBusy(false)}}
  function navigate(next:Page){setPage(next);setError('');setNotice('');setReview(null);setReceipt(null);setDestination('')}
  const transactionList=(rows:Entry[])=>rows.length?<ul className="bank-transactions">{rows.map(t=><li key={t.id}><span className="bank-entry-icon">{t.amount_minor<0?'↗':'↙'}</span><div><strong>{t.kind==='SANDBOX_FUNDING'?'Sandbox funding':t.amount_minor<0?'Internal transfer sent':'Internal transfer received'}</strong><small>{new Date(t.created_at).toLocaleString()} · {t.status}</small><code>{t.reference}</code></div><strong className={t.amount_minor>0?'credit':''}>{money(t.amount_minor,t.currency)}</strong></li>)}</ul>:<div className="bank-empty"><h3>No transactions yet</h3><p>Your real ledger activity will appear here after explicit sandbox funding or a transfer.</p></div>
  return <div className="bank-app"><div className="bank-sandbox">SANDBOX · DEMO ENVIRONMENT — NO REAL MONEY</div><header className="bank-header"><a href="/bank/" className="bank-wordmark"><span>╱╱</span> NEXUS <b>BANK</b></a><span className="bank-header-note">A clearer way to bank. A controlled place to learn.</span>{profile&&<button onClick={logout} disabled={busy}>Sign out</button>}</header>
  {loading?<main className="bank-auth" role="status">Connecting to your sandbox…</main>:!profile?<main className="bank-auth"><section className="bank-auth-story"><span className="bank-eyebrow">YOUR EVERYDAY, SIMULATED.</span><h1>Banking that<br/>starts with you.</h1><p>Open your sandbox account. Move simulated funds. See every transaction, with a protection layer working behind the scenes.</p><div className="bank-story-note">No real money. No real banking details.<br/>Use a fictional display name and a unique demo password.</div></section><section className="bank-auth-form"><span className="bank-eyebrow">NEXUS BANK SANDBOX</span><h2>{register?'Make room for a fresh start.':'Good to see you again.'}</h2><p>{register?'Your account opens with zero funds and no invented activity.':'Sign in to your own account and pick up where you left off.'}</p>{error&&<div className="bank-error" role="alert">{error}</div>}<form onSubmit={authenticate}>{register&&<label>Fictional display name<input required maxLength={60} value={name} onChange={e=>setName(e.target.value)} autoComplete="off"/></label>}<label>Sandbox username<input required minLength={3} maxLength={100} pattern="[A-Za-z0-9_.@+\-]+" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username"/></label><label>Demo password<input required type="password" minLength={12} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} autoComplete={register?'new-password':'current-password'}/><small>At least 12 characters. Do not reuse a real password.</small></label><button className="bank-primary" disabled={busy}>{busy?'Please wait…':register?'Create sandbox account':'Sign in'} <span>↗</span></button></form><button className="bank-switch" onClick={()=>{setRegister(!register);setError('');setPassword('')}} disabled={busy}>{register?'Already have an account? Sign in':'New here? Open a sandbox account'}</button></section></main>:<>
  <nav className="bank-nav" aria-label="Bank navigation">{(['overview','account','transactions','beneficiaries','transfer'] as Page[]).map(p=><button key={p} aria-current={page===p?'page':undefined} onClick={()=>navigate(p)}>{p==='account'?'Account details':p[0].toUpperCase()+p.slice(1)}</button>)}</nav><main className="bank-main"><div className="bank-greeting"><div><span className="bank-eyebrow">YOUR NEXUS BANK</span><h1>{page==='overview'?`Hello, ${profile.display_name}.`:page==='account'?'Your account.':page==='transactions'?'Every move, accounted for.':page==='beneficiaries'?'Your trusted recipients.':'A simple, internal transfer.'}</h1></div><button disabled={busy} onClick={()=>{setBusy(true);void reload().catch(r=>setError(r.message)).finally(()=>setBusy(false))}}>↻ Refresh</button></div>{error&&<div className="bank-error" role="alert">{error}</div>}{notice&&<div className="bank-success" role="status">{notice}</div>}
  {!account?<div className="bank-empty">{busy?'Loading your account…':'Your account could not be loaded. Refresh to try again.'}</div>:<>
  {(page==='overview'||page==='account')&&<><div className="bank-overview-grid"><section className="bank-balance"><div className="bank-balance-top"><span>{account.account_type.replaceAll('_',' ')}</span><span>{account.status}</span></div><small>Available sandbox balance</small><div className="bank-amount">{money(account.available_balance_minor,account.currency)}</div><p>{account.masked_account_reference} <span>· {account.currency}</span></p><div className="bank-balance-actions"><button onClick={()=>navigate('transfer')}>Make a transfer ↗</button><button onClick={()=>navigate('account')}>Account details →</button></div></section><section className="bank-account-card"><span className="bank-eyebrow">YOURS TO SHARE IN THIS SANDBOX</span><h2>Your account reference</h2><p>Use this identifier when another sandbox customer adds you as a beneficiary. It is not a real bank account number.</p><code>{account.account_id}</code><button onClick={()=>{void navigator.clipboard?.writeText(account.account_id).then(()=>setNotice('Sandbox account ID copied.')).catch(()=>setNotice('Select the account ID above to copy it.'))}}>Copy sandbox account ID</button></section></div>{page==='account'&&<section className="bank-panel"><h2>Account information</h2><dl className="bank-details"><div><dt>Account holder</dt><dd>{account.display_name}</dd></div><div><dt>Account type</dt><dd>{account.account_type}</dd></div><div><dt>Currency</dt><dd>{account.currency}</dd></div><div><dt>Status</dt><dd>{account.status}</dd></div><div><dt>Account reference</dt><dd>{account.masked_account_reference}</dd></div></dl></section>}<section className="bank-panel"><div className="bank-panel-heading"><h2>Recent activity</h2><button onClick={()=>navigate('transactions')}>View all transactions →</button></div>{transactionList(account.recent_transactions)}</section></>}
  {page==='transactions'&&<section className="bank-panel"><div className="bank-panel-heading"><h2>Transaction history</h2><small>Entries {offset+1}–{offset+entries.length}</small></div>{transactionList(entries)}<div className="bank-pagination"><button onClick={()=>void paginate(Math.max(0,offset-20))} disabled={busy||offset===0}>← Previous</button><button onClick={()=>void paginate(offset+20)} disabled={busy||entries.length<20}>Next →</button></div></section>}
  {page==='beneficiaries'&&<div className="bank-form-grid"><section className="bank-panel"><h2>Add an internal beneficiary</h2><p>Only eligible accounts in this sandbox can receive transfers.</p><form onSubmit={addBeneficiary}><label>Recipient sandbox account ID<input required inputMode="numeric" pattern="[0-9]{12}" minLength={12} maxLength={12} value={destination} onChange={e=>setDestination(e.target.value)}/></label><label>Your label for this recipient<input required maxLength={60} value={label} onChange={e=>setLabel(e.target.value)}/></label><button className="bank-primary" disabled={busy}>{busy?'Saving…':'Save beneficiary'}</button></form></section><section className="bank-panel"><h2>Saved beneficiaries</h2>{beneficiaries.length?<ul className="bank-beneficiaries">{beneficiaries.map(b=><li key={b.id}><strong>{b.label}</strong><code>{b.destination_account_id}</code></li>)}</ul>:<div className="bank-empty">No saved beneficiaries yet.</div>}</section></div>}
  {page==='transfer'&&<div className="bank-form-grid"><section className="bank-panel"><h2>Transfer sandbox funds</h2><p>No fees, no real money, no external banking rails.</p><form onSubmit={prepare}><label>From your account<select value={account.account_id} disabled={busy||!!review} onChange={e=>{void loadAccount(e.target.value)}}>{accounts.map(a=><option key={a.account_id} value={a.account_id}>{a.masked_account_reference}</option>)}</select></label><label>Saved beneficiary<select value={beneficiaries.find(b=>b.destination_account_id===destination)?.destination_account_id||''} disabled={busy||!!review} onChange={e=>setDestination(e.target.value)}><option value="">Enter a destination below</option>{beneficiaries.map(b=><option key={b.id} value={b.destination_account_id}>{b.label}</option>)}</select></label><label>Destination sandbox account ID<input required inputMode="numeric" pattern="[0-9]{12}" minLength={12} maxLength={12} value={destination} disabled={busy||!!review} onChange={e=>setDestination(e.target.value)}/></label><label>Amount in INR<input required inputMode="decimal" value={amount} placeholder="0.00" disabled={busy||!!review} onChange={e=>setAmount(e.target.value)}/><small>Available: {money(account.available_balance_minor)}</small></label><button className="bank-primary" disabled={busy||!!review}>Review transfer →</button></form></section><section className="bank-panel bank-transfer-review">{receipt?<><span className="bank-receipt-icon">✓</span><span className="bank-eyebrow">TRANSFER RECEIPT</span><h2>Sandbox transfer completed.</h2><strong className="bank-receipt-amount">{money(receipt.amount_minor,receipt.currency)}</strong><p>Status: {receipt.status}</p><code>{receipt.reference}</code><button onClick={()=>navigate('transactions')}>View transaction history →</button></>:review?<><span className="bank-eyebrow">PLEASE CHECK BEFORE CONFIRMING</span><h2>{money(review.amount_minor)} to your recipient</h2><p>Destination sandbox account</p><code>{review.destination_account_id}</code><p>This action transfers simulated funds. Repeated confirmation uses the same idempotency key.</p><button className="bank-primary" disabled={busy} onClick={()=>void confirm()}>{busy?'Processing…':'Confirm sandbox transfer'}</button><button disabled={busy} onClick={()=>setReview(null)}>Edit details</button></>:<div className="bank-empty"><h3>You stay in control.</h3><p>Review the recipient and amount here before any transfer is submitted.</p></div>}</section></div>}
  </>}</main></>}
  <footer className="bank-footer"><span>NEXUS BANK · Simulated funds only. No licensed banking services.</span><span>Protected paths by VEILMINT</span>{correlation&&<code title="Share this request ID with the local operator">Request {correlation}</code>}</footer></div>
}
