import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import BankApp from './BankApp'
afterEach(()=>vi.unstubAllGlobals())
test('registration is explicit and never claims preloaded balances',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:401,headers:new Headers(),json:async()=>({})}))
  render(<BankApp/>);await screen.findByRole('button',{name:'New here? Open a sandbox account'})
  await userEvent.click(screen.getByRole('button',{name:'New here? Open a sandbox account'}))
  expect(screen.getByLabelText('Fictional display name')).toBeInTheDocument()
  expect(screen.getByText('Your account opens with zero funds and no invented activity.')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:/Create sandbox account/})).toBeInTheDocument()
})
test('real empty ledger state and account values come from responses',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,headers:new Headers(),json:async()=>path.endsWith('/customers/me')?{customer_id:'demo',display_name:'API supplied name'}:path.endsWith('/accounts')?[{account_id:'account',masked_account_reference:'•••• TEST'}]:path.includes('/transactions')||path.endsWith('/beneficiaries')?[]:{account_id:'account',display_name:'API supplied name',account_type:'SANDBOX_CURRENT',currency:'INR',status:'ACTIVE',masked_account_reference:'•••• TEST',available_balance_minor:4321,recent_transactions:[]}})))
  render(<BankApp/>);expect(await screen.findByText('Hello, API supplied name.')).toBeInTheDocument();expect(screen.getByText('No transactions yet')).toBeInTheDocument();expect(screen.getByText(/43.21/)).toBeInTheDocument()
})
