import { render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach,expect,test,vi } from 'vitest'
import ConsumerLab from './ConsumerLab'
import { DashboardModeProvider,DashboardModeToggle } from './DashboardMode'
afterEach(()=>{vi.unstubAllGlobals();sessionStorage.clear()})
test('lab invokes actual API adapter, renders same-source toggle and clears old consumer results',async()=>{
 const paths:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  paths.push(path)
  let result:unknown=path.startsWith('/api/operator/accounts')?{accounts:[{account_id:'123456789012'}]}:{policy:null,history:[],report:{}}
  if(path.endsWith('/run')){
   const body=JSON.parse(String(init?.body))
   result={account_id:body.account_id,trace_id:'real-test-trace',source_version:'same-source-hash',consumer_id:body.consumer,actual_runtime_mode:body.mode,policy_revision:'r1',policy_valid:true,baseline:{preview:{account_id:'123456789012',email:'demo@bank.example'},field_paths:['/account_id','/email'],byte_count:60},protected:{preview:{account_id:'123456789012'},field_paths:['/account_id'],byte_count:30},consumer_result:{eligible:true},decisions:[],log:{record_id:1},warnings:[]}
  }
  return {ok:true,json:async()=>result}
 }))
 const user=userEvent.setup()
 render(<DashboardModeProvider><DashboardModeToggle/><ConsumerLab/></DashboardModeProvider>)
 await screen.findByRole('option',{name:'123456789012'})
 await user.selectOptions(screen.getByLabelText('Producer account'),'123456789012')
 await waitFor(()=>expect(screen.getByRole('button',{name:'Invoke consumer →'})).toBeEnabled())
 await user.click(screen.getByRole('button',{name:'Invoke consumer →'}))
 expect(await screen.findByLabelText('Consumer comparison JSON')).toHaveTextContent('demo@bank.example')
 await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
 expect(screen.getByLabelText('Consumer comparison JSON')).not.toHaveTextContent('demo@bank.example')
 expect(paths.filter(p=>p.endsWith('/run'))).toHaveLength(1)
 await user.selectOptions(screen.getByLabelText('Scenario consumer'),'notifications')
 expect(screen.queryByLabelText('Consumer comparison JSON')).not.toBeInTheDocument()
 expect(await screen.findByText('Select a producer and invoke a consumer')).toBeInTheDocument()
})
