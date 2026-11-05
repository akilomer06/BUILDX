import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'
import { request } from './api'
afterEach(() => vi.unstubAllGlobals())
test('backend failure is shown without its private exception', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('PRIVATE_VALUE')))
  render(<App />)
  expect(await screen.findByRole('alert')).toHaveTextContent('backend is unavailable')
  expect(screen.queryByText('PRIVATE_VALUE')).not.toBeInTheDocument()
})
test('stale review reports a safe reload instruction', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:false,status:409}))
  await expect(request('/api/policy/review', {})).rejects.toThrow('Refresh before continuing')
})
test('review requests preserve revision binding and explicit selection', async () => {
  const fetcher = vi.fn().mockResolvedValue({ok:true,json:async()=>({saved:true})})
  vi.stubGlobal('fetch',fetcher)
  const body = {revision_id:'r1',analysis_digest:'a',inputs_digest:'b',approved_fields:['secret'],reviewer:'Synthetic'}
  await request('/api/policy/review', body)
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(body)
})

test('candidate removal controls require reviewer and preview while used fields stay disabled', async () => {
  const fields=[{name:'account_id',usage:'USED',sensitivity:'INTERNAL',evidence:['Direct read']},{name:'secret',usage:'CANDIDATE_UNUSED',sensitivity:'HIGH',evidence:['Candidate only']},{name:'risk',usage:'UNKNOWN',sensitivity:'INTERNAL',evidence:['Dynamic']}]
  const analysis={fields,counts:{USED:1,CANDIDATE_UNUSED:1,UNKNOWN:1},warnings:[],analysis:{scope:'Source only',consumer:'demo.py',root_name:'payload'},schema_validation:{schema_valid:true,payload_valid:true}}
  const revision={revision_id:'r1-demo',number:1,status:'REVIEW_REQUIRED',analysis_digest:'a'.repeat(64),inputs_digest:'b'.repeat(64)}
  const policy={revision,fields:fields.map(f=>({...f,removal_allowed:f.usage==='CANDIDATE_UNUSED',api_action:'KEEP',log_action:'MASK'})),summary:{api_actions:{KEEP:3,REMOVE:0},fields_before:3,fields_after:3},warnings:[],approval:null}
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('analysis')?analysis:path==='/api/traffic'?{events:[]}:{policy,history:[revision]}})))
  const user = (await import('@testing-library/user-event')).default.setup()
  render(<App/>)
  await user.click(screen.getByRole('button',{name:/Field evidence/}))
  await screen.findByText('account_id')
  await user.click(screen.getByRole('button',{name:/Policy review/}))
  expect(screen.getByRole('checkbox',{name:'Approve removal of account_id'})).toBeDisabled()
  expect(screen.getByRole('checkbox',{name:'Approve removal of risk'})).toBeDisabled()
  expect(screen.getByRole('button',{name:/Review approval/})).toBeDisabled()
  await user.click(screen.getByRole('checkbox',{name:'Approve removal of secret'}))
  await user.type(screen.getByPlaceholderText('Your reviewer label'),'Synthetic reviewer')
  await user.click(screen.getByRole('button',{name:/Review approval/}))
  expect(screen.getByRole('region',{name:'Approval summary'})).toHaveTextContent('3 → 2 fields')
  expect(screen.getByRole('button',{name:'Confirm approval'})).toBeEnabled()
})

test('one Policy review switches destination and clears previous selections',async()=>{
  const make=(kind:string)=>{
    const fields=[{name:kind+'_required',usage:'USED',sensitivity:'GENERAL',evidence:['Required by this destination']},{name:kind+'_candidate',usage:'CANDIDATE_UNUSED',sensitivity:'GENERAL',evidence:['Review candidate']}]
    const revision={revision_id:kind+'-r1',number:1,status:'REVIEW_REQUIRED',analysis_digest:'a'.repeat(64),inputs_digest:'b'.repeat(64)}
    return {analysis:{fields,counts:{USED:1,CANDIDATE_UNUSED:1,UNKNOWN:0},warnings:[],analysis:{scope:'Explicit contract',consumer:'demo.py',root_name:'payload'},schema_validation:{schema_valid:true,payload_valid:true}},envelope:{policy:{revision,fields:fields.map(f=>({...f,removal_allowed:f.usage==='CANDIDATE_UNUSED',api_action:'KEEP',log_action:'ALLOW'})),summary:{api_actions:{KEEP:2,REMOVE:0},fields_before:2,fields_after:2},warnings:[],approval:null},history:[revision]}}
  }
  const bank=make('bank'),example=make('example')
  const fetcher=vi.fn(async(path:string)=>({ok:true,json:async()=>path==='/api/traffic'?{events:[]}:path.endsWith('analysis')?(path.includes('bank-')?bank.analysis:example.analysis):path.includes('bank-policy')?bank.envelope:example.envelope}))
  vi.stubGlobal('fetch',fetcher)
  const user=(await import('@testing-library/user-event')).default.setup()
  render(<App/>)
  expect(screen.getAllByRole('button',{name:'Policy review'})).toHaveLength(1)
  expect(screen.queryByRole('button',{name:'Bank endpoint policy'})).not.toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'Policy review'}))
  await screen.findByText('bank_candidate')
  await user.click(screen.getByRole('checkbox',{name:'Approve removal of bank_candidate'}))
  await user.type(screen.getByPlaceholderText('Your reviewer label'),'Synthetic reviewer')
  await user.selectOptions(screen.getByRole('combobox',{name:'Policy destination'}),'example')
  await screen.findByText('example_candidate')
  expect(screen.getByRole('checkbox',{name:'Approve removal of example_candidate'})).not.toBeChecked()
  expect(screen.getByPlaceholderText('Your reviewer label')).toHaveValue('')
  expect(screen.queryByText('bank_candidate')).not.toBeInTheDocument()
  expect(fetcher.mock.calls.some(([p])=>p==='/api/policy')).toBe(true)
  await user.click(screen.getByRole('radio',{name:'VEILMINT'}))
  await user.click(screen.getByRole('button',{name:'Live bank traffic'}))
  expect(screen.getByRole('radio',{name:'VEILMINT'})).toBeChecked()
  expect(screen.queryByRole('button',{name:'API comparison'})).not.toBeInTheDocument()
})
