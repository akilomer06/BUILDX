import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DashboardModeToggle, useDashboardMode } from './DashboardMode'
import { fetchInspectedResponse } from './responseApi'
import type { InspectedResponse } from './responseApi'
import type { TrafficEvent } from './LiveTraffic'
import './comparison.css'
import './responseInspector.css'

function highlighted(line:string){
  const tokens=line.split(/("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g)
  return tokens.map((token,index)=><span key={index} className={/^".*:\s*$/.test(token)?'json-key':token.startsWith('"')?'json-string':/^-?\d/.test(token)?'json-number':'json-punctuation'}>{token}</span>)
}
const fieldName=(path:string)=>path.split('/').at(-1)?.replaceAll('~1','/').replaceAll('~0','~')

export default function ResponseInspector({event,onClose}:{event:TrafficEvent;onClose:()=>void}){
  const {mode}=useDashboardMode()
  const [result,setResult]=useState<InspectedResponse|null>(null)
  const [failed,setFailed]=useState<{mode:string;correlation:string}|null>(null)
  const [refresh,setRefresh]=useState(0)
  const [copied,setCopied]=useState('')
  const overlayRef=useRef<HTMLDivElement>(null)
  const dialogRef=useRef<HTMLElement>(null)
  useLayoutEffect(()=>{
    const previousFocus=document.activeElement instanceof HTMLElement?document.activeElement:null
    const previousOverflow=document.body.style.overflow
    const siblings=Array.from(document.body.children).filter((element):element is HTMLElement=>element instanceof HTMLElement&&element!==overlayRef.current)
    const previousAttributes=siblings.map(element=>({element,hidden:element.getAttribute('aria-hidden'),inert:element.getAttribute('inert')}))
    for(const element of siblings){element.setAttribute('aria-hidden','true');element.setAttribute('inert','')}
    document.body.style.overflow='hidden'
    dialogRef.current?.querySelector<HTMLButtonElement>('[data-response-close]')?.focus()
    return()=>{
      document.body.style.overflow=previousOverflow
      for(const {element,hidden,inert} of previousAttributes){
        if(hidden===null)element.removeAttribute('aria-hidden');else element.setAttribute('aria-hidden',hidden)
        if(inert===null)element.removeAttribute('inert');else element.setAttribute('inert',inert)
      }
      if(previousFocus?.isConnected)previousFocus.focus()
    }
  },[])
  useEffect(()=>{
    let active=true
    const controller=new AbortController()
    setResult(null);setFailed(null);setCopied('')
    void fetchInspectedResponse(event.correlation_id,mode,controller.signal).then(value=>{
      if(active&&value.endpoint===event.endpoint&&value.method===event.method&&value.status===event.http_status)setResult(value)
      else if(active)setFailed({mode,correlation:event.correlation_id})
    }).catch(()=>{if(active)setFailed({mode,correlation:event.correlation_id})})
    return()=>{active=false;controller.abort()}
  },[event.correlation_id,event.endpoint,event.method,event.http_status,mode,refresh])
  const current=result?.mode===mode&&result.correlationId===event.correlation_id?result:null
  const error=failed?.mode===mode&&failed.correlation===event.correlation_id
  const auth=event.endpoint.startsWith('/api/bank/auth/')
  function explore(){
    if(event.account_id)sessionStorage.setItem('veilmint-flow-account',event.account_id)
    else if(current?.data&&typeof current.data==='object'&&'account_id' in current.data&&mode==='standard'){
      sessionStorage.setItem('veilmint-flow-account',String((current.data as {account_id:unknown}).account_id))
    }
    onClose();window.dispatchEvent(new Event('veilmint:open-flow'))
  }
  async function copy(){
    if(!current)return
    try{await navigator.clipboard.writeText(JSON.stringify(current.data,null,2));setCopied('JSON copied.')}
    catch{setCopied('Select the JSON to copy it.')}
  }
  return createPortal(<div className="response-dialog-overlay" ref={overlayRef} onClick={event=>{if(event.target===event.currentTarget)onClose()}} onKeyDown={event=>{
    if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onClose()}
    if(event.key==='Tab'){
      const focusable=Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary,[tabindex="0"]')||[]).filter(element=>(!element.closest('details:not([open])')||element.tagName==='SUMMARY')&&!(element instanceof HTMLInputElement&&element.type==='radio'&&!element.checked))
      const first=focusable[0],last=focusable.at(-1)
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
    }
  }}>
  <section ref={dialogRef} className="api-comparison response-dialog-window" data-mode={mode} role="dialog" aria-modal="true" aria-labelledby="response-dialog-title" id="selected-api-response" tabIndex={-1}>
    <header className="response-dialog-heading"><div><h2 id="response-dialog-title">API response</h2><p><span className="http-method">{event.method}</span><code>{event.endpoint}</code></p></div><button className="button secondary" data-response-close onClick={onClose}>Close response <span aria-hidden="true">×</span></button></header>
    <DashboardModeToggle/>
    <div className="response-dialog-content">
    <p className="response-dialog-request">Request <code>{event.correlation_id}</code></p>
    {error?<div className="comparison-error" role="status"><h3>Response body unavailable</h3><p>{auth?'Authentication response bodies and session headers are excluded from inspection.':'Refresh the account or page in the bank website, then click its new request here. Older records have no captured body; captures expire after 15 minutes or a backend restart.'}</p>{!auth&&<button className="button secondary" onClick={()=>setRefresh(value=>value+1)}>Retry loading response</button>}</div>:!current?<div className="comparison-loading" role="status"><span className="comparison-spinner" aria-hidden="true"/>Loading this request’s {mode==='standard'?'Standard':'VEILMINT'} response…</div>:<div className="comparison-result" key={mode}>
      <div className="response-json-heading"><div><strong>JSON response body</strong><span>HTTP/{current.httpVersion} {current.status} {current.reason} · {current.responseBytes} B</span></div><button className="button secondary" onClick={()=>void copy()}>Copy JSON</button></div>
      <pre className="response-json-viewer" aria-label="Actual API JSON response" tabIndex={0}><code>{JSON.stringify(current.data,null,2).split('\n').map((line,index)=>{
        const key=line.trim().match(/^"((?:\\.|[^"\\])*)"\s*:/)?.[1]
        const masked=!!key&&current.masked.some(path=>fieldName(path)===key)
        const exposed=!!key&&current.exposed.some(path=>fieldName(path)===key)
        return <span className={'response-json-row'+(masked?' json-masked':exposed?' json-exposed':'')} key={index}><span className="response-json-number" aria-hidden="true">{String(index+1).padStart(2,'0')}</span><span className="response-json-code">{highlighted(line)}</span>{(masked||exposed)&&<span className="response-json-state" aria-hidden="true">{masked?'MASKED':'EXPOSED'}</span>}</span>
      })}</code></pre>
      <div className="response-privacy-summary" role="group" aria-label="Response privacy metrics"><span><strong>{current.masked.length}</strong> masked</span><span><strong>{current.removed.length}</strong> removed</span><span><strong>{current.reductionPercent}%</strong> smaller · {current.standardBytes} B → {current.responseBytes} B</span></div>
      <details className="response-header-details"><summary>HTTP headers</summary><pre className="response-http-headers" aria-label="HTTP response headers">{`HTTP/${current.httpVersion} ${current.status} ${current.reason}\n`+Object.entries(current.headers).map(([key,value])=>`${key}: ${value}`).join('\n')}</pre></details>
      {!!current.removed.length&&<section className="comparison-decisions" aria-label="Removed response fields"><h3>Removed before delivery</h3><div className="comparison-field-chips">{current.removed.map(path=><span key={path}>− {path}</span>)}</div></section>}
      <button className="button secondary" disabled={!event.account_id&&mode!=='standard'} onClick={explore}>Explore consumer policies for this account</button>
      <p className="comparison-source">Captured {new Date(current.capturedAt).toLocaleString()} · Same request in both modes · UTF-8 body bytes<span role="status">{copied}</span></p>
    </div>}
    </div>
  </section></div>,document.body)
}
