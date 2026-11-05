import { render, screen, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import AccountsExplorer from './AccountsExplorer'
import { RequestEvidence } from './RequestEvidence'

afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()})
const id='123456789012'
function response(path:string){
  const reveal=path.includes('reveal=true')
  const identity=reveal?'FICTIONAL_PRIVATE':'[REDACTED]'
  if(path.includes('/accounts?'))return {accounts:[{account_id:id,display_name:identity,username:identity,available_balance_minor:reveal?12345:'[REDACTED]',currency:'INR',status:'ACTIVE',masked_account_reference:'•••• DEMO'}],total:1}
  return {customer:{display_name:identity},source_record:{display_name:identity,account_number:identity},source_field_paths:['/display_name','/account_number'],contract_excluded_paths:['/account_number'],customer_dto:{display_name:identity},current_policy_preview:{output:{display_name:identity},trace:{policy_valid:false,policy_revision:null,removed_paths:[],warnings:[]},label:'Read-only preview of the current policy; no customer request or log is generated.'},ledger:[],beneficiaries:[],transfers:[],events:[],demo_profile_present:true}
}
test('account reveal expires and clears sensitive fields from the view',async()=>{
  vi.useFakeTimers()
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>response(path)})))
  render(<AccountsExplorer/>)
  await act(()=>vi.advanceTimersByTimeAsync(250))
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:id}))})
  expect(document.body).not.toHaveTextContent('FICTIONAL_PRIVATE')
  expect(screen.getByText('No linked customer request has been recorded yet. Refresh the account from the customer app, then refresh here. Opening this explorer creates no bank traffic.')).toBeInTheDocument()
  const reveal=screen.getByRole('checkbox',{name:'Reveal sandbox fields for 45 seconds'})
  await act(async()=>{fireEvent.click(reveal)})
  await act(()=>vi.advanceTimersByTimeAsync(250))
  expect(document.body).toHaveTextContent('FICTIONAL_PRIVATE')
  expect(screen.getByText('₹123.45')).toBeInTheDocument()
  await act(()=>vi.advanceTimersByTimeAsync(45000))
  await act(()=>vi.advanceTimersByTimeAsync(250))
  expect(reveal).not.toBeChecked()
  expect(document.body).not.toHaveTextContent('FICTIONAL_PRIVATE')
})
test('request evidence separates contract exclusion from approved minimizer removal',async()=>{
  const event={id:1,endpoint:'/api/bank/accounts/{account_id}',method:'GET',correlation_id:'correlation-real',policy_revision:'r2',mode:'ENFORCE',policy_valid:true,source_field_paths:['/account_number','/legacy_display_label','/available_balance_minor'],contract_excluded_paths:['/account_number'],removed_paths:['/legacy_display_label'],kept_paths:['/available_balance_minor'],log_actions:[{path:['available_balance_minor'],action:'DROP'}],warnings:[],header_actions:[{direction:'request',name:'Cookie',present:true,action:'EXCLUDE_FROM_LOG'}]}
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({event,persisted:{id:4,event:{display_name:'[REDACTED]'}}})}))
  render(<RequestEvidence eventId={1}/>)
  expect(await screen.findByText('EXCLUDED BY RESPONSE CONTRACT')).toBeInTheDocument()
  expect(screen.getByText('REMOVE · approved VEILMINT policy')).toBeInTheDocument()
  expect(screen.getByText('Present; authentication transport preserved')).toBeInTheDocument()
  expect(screen.getByLabelText('Persisted sanitized bank log')).toHaveTextContent('[REDACTED]')
})
