import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import LiveTraffic from './LiveTraffic'
import { DashboardModeProvider, DashboardModeToggle } from './DashboardMode'
import { fetchInspectedResponse } from './responseApi'

afterEach(()=>{vi.unstubAllGlobals();document.querySelector('[data-response-test-style]')?.remove()})
const events=[1,2].map(id=>({id,created_at:'2026-11-04T18:25:00Z',correlation_id:'request-'+id,
  endpoint:'/api/bank/accounts/{account_id}',method:'GET',http_status:200,policy_revision:'r1',mode:'ENFORCE',outcome:'SUCCESS',
  kept_paths:[],removed_paths:[],warnings:[],log_outcome:'SANITIZED',latency_ms:1,log_actions:[],log_record_id:id,destination:'bank'}))
function packet(mode:string,id='request-1',status=200){
  const standard={account_id:id==='request-1'?'120000000042':'120000000099',display_name:id==='request-1'?'Fictional Alice':'Fictional Bob',available_balance_minor:4500050,currency:'INR',recent_transactions:[]}
  const data=mode==='standard'?standard:{...standard,account_id:'********'+standard.account_id.slice(-4),display_name:'F******** '+(id==='request-1'?'A****':'B**')}
  const original=JSON.stringify(standard),body=JSON.stringify(data)
  const reduction=original.length-body.length
  return new Response(body,{status,headers:{'Content-Type':'application/json','X-Content-Type-Options':'nosniff',
    'Cache-Control':'no-store','X-Request-ID':id,'X-Captured-Correlation-ID':id,'X-Captured-Endpoint':'/api/bank/accounts/{account_id}',
    'X-Captured-Method':'GET','X-Captured-At':'2026-11-04T18:25:00Z','X-Captured-HTTP-Version':'1.1','X-Captured-Status-Text':'OK',
    'X-Privacy-Mode':mode,'X-Privacy-Standard-Bytes':String(original.length),'X-Privacy-Response-Bytes':String(body.length),
    'X-Privacy-Reduction-Bytes':String(reduction),'X-Privacy-Reduction-Percent':String(Math.round(10000*reduction/original.length)/100),
    'X-Privacy-Masked-Fields':mode==='veilmint'?'/account_id,/display_name':'','X-Privacy-Removed-Fields':'',
    'X-Privacy-Exposed-Fields':mode==='standard'?'/account_id,/display_name':''}})
}
function setup(fetcher=(url:string)=>Promise.resolve(url==='/api/traffic'?new Response(JSON.stringify({events})):packet(url.endsWith('standard')?'standard':'veilmint',url.includes('request-2')?'request-2':'request-1'))){
  vi.stubGlobal('fetch',vi.fn(fetcher))
  return render(<DashboardModeProvider><DashboardModeToggle/><LiveTraffic/></DashboardModeProvider>)
}
function row(id:string){return screen.getByText(id).closest('tr')!}

test('clicking a traffic row opens a response dialog with the entire JSON and five mode cycles',async()=>{
  const user=userEvent.setup()
  setup()
  await screen.findByText('request-1')
  expect(screen.queryByLabelText('Actual API JSON response')).not.toBeInTheDocument()
  await user.click(within(row('request-1')).getByRole('button'))
  const dialog=screen.getByRole('dialog',{name:'API response'})
  expect(dialog).toHaveAttribute('aria-modal','true')
  expect(dialog.closest('table')).toBeNull()
  expect(await screen.findByLabelText('Actual API JSON response')).toHaveTextContent('120000000042')
  const structured=Array.from(screen.getByLabelText('Actual API JSON response').querySelectorAll('.response-json-code')).map(line=>line.textContent).join('\n')
  expect(JSON.parse(structured)).toEqual(await packet('standard').json())
  expect(structured.trim().startsWith('{')).toBe(true)
  expect(structured.trim().endsWith('}')).toBe(true)
  expect(dialog.querySelector('details')).not.toHaveAttribute('open')
  await user.click(within(dialog).getByText('HTTP headers',{selector:'summary'}))
  expect(screen.getByLabelText('HTTP response headers')).toHaveTextContent('HTTP/1.1 200 OK')
  expect(screen.getByLabelText('HTTP response headers')).toHaveTextContent('Content-Type: application/json')
  expect(screen.getByLabelText('HTTP response headers')).toHaveTextContent('X-Content-Type-Options: nosniff')
  for(let i=0;i<5;i++){
    await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
    await waitFor(()=>expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent('********0042'))
    expect(screen.getByLabelText('Actual API JSON response')).not.toHaveTextContent('Fictional Alice')
    expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent('4500050')
    expect(screen.getByLabelText('Actual API JSON response').querySelectorAll('.json-masked')).toHaveLength(2)
    expect(screen.getByRole('group',{name:'Response privacy metrics'})).toHaveTextContent('2 masked')
    await user.click(screen.getByRole('radio',{name:'Standard'}))
    await waitFor(()=>expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent('120000000042'))
  }
  await user.click(screen.getByRole('button',{name:'Close response'}))
  // A different row opens that row's JSON in a new box.
  await user.click(within(row('request-2')).getByRole('button'))
  expect(await screen.findByLabelText('Actual API JSON response')).toHaveTextContent('Fictional Bob')
  expect(screen.getByLabelText('Actual API JSON response')).not.toHaveTextContent('Fictional Alice')
  await user.click(screen.getByRole('button',{name:'Close response'}))
  expect(screen.queryByLabelText('Actual API JSON response')).not.toBeInTheDocument()
})

test('late Standard and previous-row responses cannot replace the current protected JSON',async()=>{
  let finish:(value:Response)=>void=()=>{}
  setup(url=>{
    if(url==='/api/traffic')return Promise.resolve(new Response(JSON.stringify({events})))
    if(url.includes('request-1')&&url.endsWith('standard'))return new Promise(resolve=>{finish=resolve})
    return Promise.resolve(packet(url.endsWith('standard')?'standard':'veilmint',url.includes('request-2')?'request-2':'request-1'))
  })
  await screen.findByText('request-1')
  fireEvent.click(within(row('request-1')).getByRole('button'))
  fireEvent.click(screen.getByRole('radio',{name:'VEILMINT'}))
  expect(await screen.findByLabelText('Actual API JSON response')).toHaveTextContent('********0042')
  fireEvent.click(screen.getByRole('button',{name:'Close response'}))
  fireEvent.click(within(row('request-2')).getByRole('button'))
  expect(await screen.findByLabelText('Actual API JSON response')).toHaveTextContent('********0099')
  await act(async()=>finish(packet('standard')))
  expect(screen.getByLabelText('Actual API JSON response')).not.toHaveTextContent('120000000042')
  expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent('********0099')
})

test('unavailable historical bodies are explained without making up JSON or metrics',async()=>{
  setup(url=>Promise.resolve(url==='/api/traffic'?new Response(JSON.stringify({events})):new Response('{}',{status:404})))
  await screen.findByText('request-1')
  fireEvent.click(within(row('request-1')).getByRole('button'))
  expect(await screen.findByText('Response body unavailable')).toBeInTheDocument()
  expect(screen.getByText(/Older records have no captured body/)).toBeInTheDocument()
  expect(screen.queryByLabelText('Actual API JSON response')).not.toBeInTheDocument()
  expect(screen.queryByRole('group',{name:'Response privacy metrics'})).not.toBeInTheDocument()
})

test('copy yields valid selected JSON; mode-specific requests never fetch a standalone demo',async()=>{
  const user=userEvent.setup()
  const clipboard=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue()
  setup()
  await screen.findByText('request-1')
  await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
  within(row('request-1')).getByRole('button').focus()
  await user.keyboard('{Enter}')
  await screen.findByLabelText('Actual API JSON response')
  await user.click(screen.getByRole('button',{name:'Copy JSON'}))
  expect(JSON.parse(clipboard.mock.calls[0][0]).account_id).toBe('********0042')
  const calls=vi.mocked(fetch).mock.calls.map(([url])=>String(url))
  expect(calls).toContain('/api/operator/responses/request-1/veilmint')
  expect(calls.some(url=>url.includes('/api/demo/'))).toBe(false)
  expect(calls.some(url=>url.endsWith('/standard'))).toBe(false)
})

test('reader rejects a response for another correlation ID',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>packet('veilmint','request-2')))
  await expect(fetchInspectedResponse('request-1','veilmint',new AbortController().signal)).rejects.toThrow('unavailable')
})

test('JSON rows use a vertical grid and wrapping instead of full-width inline boxes',async()=>{
  const style=document.createElement('style')
  style.dataset.responseTestStyle='true'
  style.textContent=readFileSync('src/responseInspector.css','utf8')
  document.head.appendChild(style)
  setup()
  await screen.findByText('request-1')
  fireEvent.click(within(row('request-1')).getByRole('button'))
  const json=await screen.findByLabelText('Actual API JSON response')
  const rows=json.querySelectorAll<HTMLElement>('.response-json-row')
  expect(rows).toHaveLength(7)
  for(const row of rows){
    expect(getComputedStyle(row).display).toBe('grid')
    expect(getComputedStyle(row.querySelector('.response-json-code')!).whiteSpace).toBe('pre-wrap')
    expect(getComputedStyle(row.querySelector('.response-json-code')!).overflowWrap).toBe('anywhere')
  }
  expect(getComputedStyle(json).overflow).toBe('visible')
  expect(getComputedStyle(json.querySelector('code')!).minWidth).toBe('0px')
})

test('Escape and backdrop close the box, restore focus and unlock the page',async()=>{
  const user=userEvent.setup()
  setup()
  await screen.findByText('request-1')
  const trigger=within(row('request-1')).getByRole('button')
  await user.click(trigger)
  await screen.findByLabelText('Actual API JSON response')
  expect(document.body.style.overflow).toBe('hidden')
  expect(screen.getByRole('button',{name:'Close response'})).toHaveFocus()
  await user.keyboard('{Shift>}{Tab}{/Shift}')
  expect(screen.getByRole('button',{name:'Explore consumer policies for this account'})).toHaveFocus()
  await user.keyboard('{Tab}')
  expect(screen.getByRole('button',{name:'Close response'})).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
  expect(document.body.style.overflow).not.toBe('hidden')
  await user.click(trigger)
  await screen.findByLabelText('Actual API JSON response')
  fireEvent.click(screen.getByRole('dialog').parentElement!)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

test('the complete nested JSON structure preserves arrays, escapes, Unicode and nulls',async()=>{
  const source={account_id:'120000000042',recent_transactions:[{id:'transaction-1',amount_minor:-1234,reference:'Fictional "quoted" reference\nnext line'}],metadata:{message:'Fictional परीक्षण',active:true,nothing:null}}
  const body=JSON.stringify(source)
  const headers=new Headers(packet('standard').headers)
  const length=new TextEncoder().encode(body).byteLength
  headers.set('X-Privacy-Standard-Bytes',String(length));headers.set('X-Privacy-Response-Bytes',String(length))
  setup(url=>Promise.resolve(url==='/api/traffic'?new Response(JSON.stringify({events})):new Response(body,{headers})))
  await screen.findByText('request-1')
  fireEvent.click(within(row('request-1')).getByRole('button'))
  const json=await screen.findByLabelText('Actual API JSON response')
  const displayed=Array.from(json.querySelectorAll('.response-json-code')).map(line=>line.textContent).join('\n')
  expect(displayed).toBe(JSON.stringify(source,null,2))
  expect(JSON.parse(displayed)).toEqual(source)
})
