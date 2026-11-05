import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { execFileSync } from 'node:child_process'
import BankApp from './BankApp'
import OperatorApp from '../App'

// Opt-in real HTTP integration using a dedicated temporary backend database.
// No browser mocks, fixed balances, seeded customers or production credentials.
test.skipIf(!process.env.NEXUS_E2E_URL)('customer forms drive real registration, beneficiary, transfer and both ledgers',async()=>{
  const base=process.env.NEXUS_E2E_URL!
  const nativeFetch=globalThis.fetch
  let cookie=''
  const ids:string[]=[]
  vi.stubGlobal('fetch',async(input:string,init?:RequestInit)=>{
    const headers=new Headers(init?.headers)
    if(cookie)headers.set('Cookie',cookie)
    const response=await nativeFetch(base+input,{...init,headers})
    const value=response.headers.get('set-cookie')?.match(/nexus_session=([^;]*)/)
    if(value)cookie='nexus_session='+value[1]
    const id=response.headers.get('X-Request-ID');if(id)ids.push(id)
    return response
  })
  const user=userEvent.setup()
  const suffix=Date.now().toString(36)
  const alice='alice.'+suffix, bob='bob.'+suffix
  const password='Sandbox-'+suffix+'-Unique-Only'
  render(<BankApp/>)
  async function credentials(username:string){
    await user.clear(screen.getByLabelText('Sandbox username'))
    await user.type(screen.getByLabelText('Sandbox username'),username)
    await user.type(screen.getByLabelText(/Demo password/),password)
  }
  async function register(username:string,name:string){
    await user.click(await screen.findByRole('button',{name:'New here? Open a sandbox account'}))
    await user.clear(screen.getByLabelText('Fictional display name'))
    await user.type(screen.getByLabelText('Fictional display name'),name)
    await credentials(username)
    await user.click(screen.getByRole('button',{name:/Create sandbox account/}))
    await screen.findByText('Hello, '+name+'.',{}, {timeout:10000})
    return (await screen.findByText(/^[0-9]{12}$/,{}, {timeout:10000})).textContent!
  }
  async function logout(){await user.click(screen.getByRole('button',{name:'Sign out'}));await screen.findByRole('button',{name:'New here? Open a sandbox account'})}
  const source=await register(alice,'Fictional Alice')
  await logout()
  const destination=await register(bob,'Fictional Bob')
  await logout()
  await credentials(alice);await user.click(screen.getByRole('button',{name:/^Sign in/}))
  await screen.findByText('Hello, Fictional Alice.')
  execFileSync(process.env.NEXUS_TEST_PYTHON!,['-m','veilmint','bank','fund','--account',source,'--amount-minor','10000','--reference','ui-test-'+suffix,'--sandbox-funds'],{env:{...process.env,VEILMINT_DB:process.env.NEXUS_E2E_DB},stdio:'pipe'})
  await user.click(screen.getByRole('button',{name:/Refresh/}))
  await screen.findAllByText(/100.00/)
  await user.click(screen.getByRole('button',{name:'Beneficiaries'}))
  await user.type(screen.getByLabelText('Recipient sandbox account ID'),destination)
  await user.type(screen.getByLabelText('Your label for this recipient'),'Fictional Bob')
  await user.click(screen.getByRole('button',{name:'Save beneficiary'}))
  await screen.findByText('Beneficiary saved.')
  await user.click(screen.getByRole('button',{name:'Transfer'}))
  await user.selectOptions(screen.getByLabelText('Saved beneficiary'),destination)
  await user.type(screen.getByLabelText(/Amount in INR/),'12.34')
  await user.click(screen.getByRole('button',{name:/Review transfer/}))
  await user.click(screen.getByRole('button',{name:'Confirm sandbox transfer'}))
  await screen.findByText('Sandbox transfer completed.',{}, {timeout:10000})
  await user.click(screen.getByRole('button',{name:'View transaction history →'}))
  expect(await screen.findByText('Internal transfer sent')).toBeInTheDocument()
  await logout();await credentials(bob);await user.click(screen.getByRole('button',{name:/^Sign in/}))
  await screen.findByText('Hello, Fictional Bob.')
  expect(await screen.findByText('Internal transfer received')).toBeInTheDocument()
  expect(screen.getAllByText(/12.34/).length).toBeGreaterThan(0)
  expect(new Set(ids).size).toBeGreaterThan(15)
  cleanup()
  render(<OperatorApp/>)
  await user.click(screen.getByRole('button',{name:'Accounts Explorer'}))
  await user.click(await screen.findByRole('button',{name:source},{timeout:10000}))
  expect(await screen.findByLabelText('Bank source record')).toHaveTextContent('[REDACTED]')
  expect(screen.getByLabelText('Bank source record')).not.toHaveTextContent('Fictional Alice')
  await user.click(screen.getByRole('checkbox',{name:'Reveal sandbox fields for 45 seconds'}))
  await waitFor(()=>expect(screen.getByLabelText('Bank source record')).toHaveTextContent('Fictional Alice'),{timeout:10000})
  expect(screen.getAllByRole('button',{name:'Policy review'})).toHaveLength(1)
  vi.unstubAllGlobals()
},60000)

test.skipIf(!process.env.NEXUS_E2E_URL)('clicking live traffic renders that actual HTTP response in both dashboard modes',async()=>{
  const base=process.env.NEXUS_E2E_URL!
  const nativeFetch=globalThis.fetch
  const username='inspection.'+Date.now().toString(36)
  const password='SYNTHETIC-Only-'+Date.now().toString(36)
  async function bankPost(path:string,body:unknown,cookie=''){
    return nativeFetch(base+'/api/bank'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Request':'1',...(cookie?{Cookie:cookie}:{})},body:JSON.stringify(body)})
  }
  const registered=await bankPost('/auth/register',{display_name:'Fictional live inspector',username,password})
  const account=(await registered.json()).account_id
  const login=await bankPost('/auth/login',{username,password})
  const cookie='nexus_session='+login.headers.get('set-cookie')!.match(/nexus_session=([^;]+)/)![1]
  const actual=await nativeFetch(base+'/api/bank/accounts/'+account,{headers:{Cookie:cookie}})
  const original=await actual.json()
  const correlation=actual.headers.get('X-Request-ID')!
  const paths:string[]=[]
  const initialUrl=window.location.href
  vi.stubGlobal('fetch',async(path:string,init?:RequestInit)=>{paths.push(path);return nativeFetch(base+path,init)})
  const user=userEvent.setup()
  render(<OperatorApp/>)
  await screen.findByText(correlation)
  expect(screen.queryByRole('button',{name:'API comparison'})).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Actual API JSON response')).not.toBeInTheDocument()
  await user.click(screen.getByText(correlation).closest('tr')!.querySelector('button')!)
  expect(screen.getByRole('dialog',{name:'API response'})).toBeVisible()
  expect(await screen.findByLabelText('Actual API JSON response')).toHaveTextContent(account)
  const actualStructure=Array.from(screen.getByLabelText('Actual API JSON response').querySelectorAll('.response-json-code')).map(line=>line.textContent).join('\n')
  expect(JSON.parse(actualStructure)).toEqual(original)
  await user.click(screen.getByText('HTTP headers',{selector:'summary'}))
  expect(screen.getByLabelText('HTTP response headers')).toHaveTextContent('HTTP/1.1 200 OK')
  for(let i=0;i<3;i++){
    await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
    await waitFor(()=>expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent('********'+account.slice(-4)))
    expect(screen.getByLabelText('Actual API JSON response')).not.toHaveTextContent(account)
    expect(screen.getByLabelText('Actual API JSON response')).not.toHaveTextContent('Fictional live inspector')
    expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent(String(original.available_balance_minor))
    await user.click(screen.getByRole('radio',{name:'Standard'}))
    await waitFor(()=>expect(screen.getByLabelText('Actual API JSON response')).toHaveTextContent(account))
  }
  expect(window.location.href).toBe(initialUrl)
  expect(paths.some(path=>path.startsWith('/api/demo/'))).toBe(false)
  expect(paths.filter(path=>path.endsWith('/veilmint')).length).toBe(3)
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  // The customer's response contract is unchanged by the operator mode.
  const unchanged=await nativeFetch(base+'/api/bank/accounts/'+account,{headers:{Cookie:cookie}})
  expect((await unchanged.json()).account_id).toBe(account)
  vi.unstubAllGlobals()
},30000)

test.skipIf(!process.env.NEXUS_E2E_URL)('operator prepares and explicitly approves a real consumer policy before minimization',async()=>{
 const base=process.env.NEXUS_E2E_URL!,nativeFetch=globalThis.fetch
 const registered=await nativeFetch(base+'/api/bank/auth/register',{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Request':'1'},body:JSON.stringify({display_name:'FICTIONAL CONSUMER UI','username':'consumer.ui.'+Date.now(),'password':'SYNTHETIC-Consumer-UI-Password'})})
 const account=(await registered.json()).account_id
 vi.stubGlobal('fetch',(path:string,init?:RequestInit)=>nativeFetch(base+path,init))
 const user=userEvent.setup()
 render(<OperatorApp/>);await user.click(screen.getByRole('button',{name:'Data Flow Explorer'}))
 await screen.findByRole('option',{name:account});await user.selectOptions(screen.getByLabelText('Producer account'),account)
 await user.click(screen.getByRole('button',{name:'Attach fictional DEMO profile'}))
 await screen.findByLabelText('Consumer comparison JSON')
 await user.selectOptions(screen.getByLabelText('Scenario consumer'),'payments')
 await user.click(screen.getByRole('button',{name:'Consumer Policy Studio'}))
 await user.click(await screen.findByRole('button',{name:'Prepare policy revision'}))
 await user.click(await screen.findByRole('button',{name:'Select all candidates'}))
 await user.type(screen.getByPlaceholderText('Your reviewer label'),'Explicit isolated UI TEST reviewer')
 await user.click(screen.getByRole('button',{name:/Review approval/}))
 await user.click(screen.getByRole('button',{name:'Confirm approval'}))
 await screen.findByText(/Decision recorded by/)
 await waitFor(()=>expect(screen.getByRole('button',{name:'Invoke consumer →'})).toBeEnabled())
 await user.click(screen.getByRole('button',{name:'Invoke consumer →'}))
 expect(await screen.findByLabelText('Consumer comparison JSON')).toHaveTextContent('support_notes')
 await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
 expect(screen.getByLabelText('Consumer comparison JSON')).not.toHaveTextContent('support_notes')
 expect(screen.getByLabelText('Consumer comparison JSON')).not.toHaveTextContent('email')
 expect(screen.getByLabelText('Consumer comparison JSON')).toHaveTextContent('branch_code')
 await user.click(screen.getByRole('button',{name:'Run scoped canaries'}))
 const heading=await screen.findByText('Scoped canary execution')
 await waitFor(()=>expect(heading.parentElement).toHaveTextContent('PASS'))
 vi.unstubAllGlobals()
},30000)
