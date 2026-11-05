import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { request } from './api'
import LiveTraffic from './LiveTraffic'
import CloudHostStatus from './CloudHostStatus'
import ConsumerLab from './ConsumerLab'
import AccountsExplorer from './AccountsExplorer'
import { DashboardModeProvider, DashboardModeToggle } from './DashboardMode'
import type { Analysis, ApiInspection, FieldEvidence, LogInspection, Mode, Policy, PolicyEnvelope, Usage, Verification } from './api'

type View = 'flow' | 'traffic' | 'accounts' | 'evidence' | 'policy' | 'inspector' | 'examples'
const usageLabel: Record<Usage, string> = { USED: 'Used', CANDIDATE_UNUSED: 'Review candidate', UNKNOWN: 'Unknown' }
const titles: Record<View, [string, string]> = {
  flow: ['Data Flow Explorer', 'One canonical producer. Distinct evidence-bound consumer policies.'],
  traffic: ['Live bank traffic', 'Real requests, contract exclusions, approved removals and protected logs.'],
  accounts: ['Accounts Explorer', 'Read-only bank records and related request evidence, masked by default.'],
  evidence: ['Field evidence map', 'Usage and sensitivity for the selected destination contract.'],
  policy: ['Policy review', 'One review workflow, explicitly scoped to its destination.'],
  inspector: ['Bank protection inspector', 'Inspect a current preview and actual persisted customer-request evidence.'],
  examples: ['Demo examples', 'The original ten-field fixture remains separate from current customer traffic.'],
}

function Icon({ name, size = 18 }: { name: View | 'canary' | 'shield' | 'refresh' | 'arrow' | 'check' | 'lock'; size?: number }) {
  const paths: Record<string, ReactNode> = {
    flow: <><path d="M3 12h6m6-6h6m-6 12h6M9 12l6-6M9 12l6 6"/></>,
    accounts: <><rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 10h18M9 10v10"/></>,
    inspector: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6"/></>,
    examples: <><path d="m8 5-6 7 6 7m8-14 6 7-6 7M14 3l-4 18"/></>,
    traffic: <><path d="M3 12h4l3-7 4 14 3-7h4" /></>,
    bankpolicy: <><path d="M4 8h16M6 8v10m6-10v10m6-10v10M3 20h18M12 3l9 5H3z" /></>,
    shield: <><path d="m12 3 7 3v6c0 4-7 8-7 8s-7-4-7-8V6z" /><path d="m8.5 11.5 2.3 2.3 4.7-5" /></>,
    evidence: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><path d="M14 15h6M14 19h6" /></>,
    policy: <><path d="M7 4h10a2 2 0 0 1 2 2v14H5V6a2 2 0 0 1 2-2Z" /><path d="m8 10 1.5 1.5L12 9M14 10h2M8 16h8" /></>,
    api: <><path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18" /></>,
    logs: <><path d="M5 5h14M5 10h14M5 15h8M5 20h8" /><path d="m16 17 2 2 4-4" /></>,
    canary: <><path d="M9 3v6l-5 8a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-8V3M7 3h10M7 14h10" /><path d="M10 17h4" /></>,
    refresh: <><path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5" /></>,
    arrow: <><path d="M4 12h15m-5-5 5 5-5 5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3" /></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>
}
function UsageBadge({ usage }: { usage: Usage }) { return <Badge tone={usage.toLowerCase()}><span className="dot" />{usageLabel[usage]}</Badge> }
function ErrorMessage({ message }: { message: string | null }) { return message ? <div className="notice error" role="alert">{message}</div> : null }
function Warnings({ warnings }: { warnings: string[] }) {
  return warnings.length ? <details className="warnings"><summary>{warnings.length} warning{warnings.length === 1 ? '' : 's'} / uncertainty notes</summary><ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details> : null
}
function JsonPanel({ title, value, note, accent = false }: { title: string; value: unknown; note?: string; accent?: boolean }) {
  return <section className={`json-panel ${accent ? 'protected' : ''}`}><div className="json-heading"><span>{title}</span><span className="mono json-label">JSON</span></div><pre tabIndex={0} aria-label={title}>{JSON.stringify(value, null, 2)}</pre>{note && <p className="panel-note">{note}</p>}</section>
}
function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol"><Icon name="shield" size={25} /></div><h3>{title}</h3><p>{children}</p></div>
}
function Evidence({ field }: { field: FieldEvidence }) {
  return <details className="field-evidence"><summary>{field.evidence[0] || 'No evidence supplied.'}</summary>{field.evidence.length > 1 && <ul>{field.evidence.slice(1).map((reason, index) => <li key={index}>{reason}</li>)}</ul>}</details>
}

function EvidenceView({ analysis, goReview }: { analysis: Analysis; goReview: () => void }) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Usage | 'ALL'>('ALL')
  const fields = analysis.fields.filter(field => (filter === 'ALL' || field.usage === filter) && field.name.toLowerCase().includes(query.toLowerCase()))
  return <>
    <div className="stats-grid">
      <div className="stat"><span>Fields inspected</span><strong>{analysis.fields.length.toString().padStart(2, '0')}</strong><small>Top-level schema inventory</small></div>
      {(['USED', 'CANDIDATE_UNUSED', 'UNKNOWN'] as Usage[]).map(usage => <div className={`stat stat-${usage.toLowerCase()}`} key={usage}><span><span className="dot" />{usageLabel[usage]}</span><strong>{analysis.counts[usage].toString().padStart(2, '0')}</strong><small>{usage === 'USED' ? analysis.analysis.mode === 'explicit_endpoint_contract' ? 'Explicit consumer contract' : 'Direct consumer evidence' : usage === 'UNKNOWN' ? 'Preserve; removal disabled' : 'Explicit approval required'}</small></div>)}
    </div>
    <div className="notice evidence-notice"><Icon name="lock" /><p><strong>Evidence sets the boundary.</strong> Candidates are not proof of non-use. Uncertain fields stay in the API response.</p><button className="text-button" onClick={goReview}>Review policy <Icon name="arrow" size={16} /></button></div>
    <section className="panel">
      <div className="panel-toolbar"><div><h2>Schema field inventory <span className="count-label">{analysis.fields.length}</span></h2><p>Usage and sensitivity are independent classifications.</p></div><label className="search"><span className="sr-only">Search fields</span><span aria-hidden="true">⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search fields…" /></label></div>
      <div className="filter-tabs" aria-label="Filter by usage">{(['ALL', 'USED', 'CANDIDATE_UNUSED', 'UNKNOWN'] as const).map(usage => <button key={usage} className={filter === usage ? 'active' : ''} onClick={() => setFilter(usage)} aria-pressed={filter === usage}>{usage === 'ALL' ? 'All fields' : usageLabel[usage]}</button>)}</div>
      <div className="table-scroll"><table><thead><tr><th>Field name</th><th>Usage evidence</th><th>Sensitivity</th><th>Reason / source</th></tr></thead><tbody>{fields.map(field => <tr key={field.name}><td><code className="field-name">{field.name}</code></td><td><UsageBadge usage={field.usage} /></td><td><span className={`sensitivity ${field.sensitivity.toLowerCase()}`}>{field.sensitivity}</span></td><td className="evidence-cell"><Evidence field={field} /></td></tr>)}</tbody></table></div>
      {!fields.length && <p className="no-results">No fields match this filter.</p>}
      <div className="table-footer"><span>{fields.length} of {analysis.fields.length} fields</span><span><span className="mint-dot" /> {analysis.analysis.mode === 'explicit_endpoint_contract' ? 'Explicit contract; TypeScript not analyzed' : 'Source parsed, never executed'}</span></div>
    </section>
    <div className="boundary"><div><span className="eyebrow">ANALYSIS BOUNDARY</span><p>{analysis.analysis.scope}</p></div><div><span>Consumer</span><code>{analysis.analysis.consumer}</code></div><div><span>Root variable</span><code>{analysis.analysis.root_name}</code></div><Badge tone="used">Schema {analysis.schema_validation.schema_valid && analysis.schema_validation.payload_valid ? 'validated' : 'not validated'}</Badge></div>
    <Warnings warnings={analysis.warnings} />
  </>
}

export function PolicyView({ envelope, onChange, endpoint = '/api/policy' }: { envelope: PolicyEnvelope; onChange: (value: PolicyEnvelope) => void; endpoint?: string }) {
  const policy = envelope.policy
  const [selected, setSelected] = useState<string[]>([])
  const [reviewer, setReviewer] = useState('')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<'APPROVE' | 'REJECT' | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reviewable = policy?.revision.status === 'REVIEW_REQUIRED'
  const candidates = policy?.fields.filter(field => field.usage === 'CANDIDATE_UNUSED' && field.removal_allowed) || []
  const prepare = async (newRevision: boolean) => {
    setBusy(true); setError(null); setPreview(null)
    try { onChange(await request<PolicyEnvelope>(endpoint + '/revisions', { new_revision: newRevision })); setSelected([]) }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const submit = async () => {
    if (!policy || !preview || !reviewer.trim()) return
    setBusy(true); setError(null)
    try {
      const result = await request<PolicyEnvelope>(endpoint + '/review', {
        revision_id: policy.revision.revision_id, analysis_digest: policy.revision.analysis_digest,
        inputs_digest: policy.revision.inputs_digest, reviewer: reviewer.trim(), notes,
        approved_fields: preview === 'APPROVE' ? selected : [], decision: preview,
      })
      onChange(result); setPreview(null); setSelected([])
    } catch (reason) { setError((reason as Error).message); setPreview(null) }
    finally { setBusy(false) }
  }
  return <>
    <ErrorMessage message={error} />
    <div className="section-bar"><div><span className="eyebrow">CURRENT POLICY</span><h2 className="revision-title">{policy ? policy.revision.revision_id : 'No policy revision'}</h2></div><div className="button-row">{policy && <Badge tone={policy.revision.status === 'APPROVED' ? 'used' : 'candidate_unused'}>{policy.revision.status.replaceAll('_', ' ')}</Badge>}<button className={policy ? 'button secondary' : 'button primary'} disabled={busy} onClick={() => prepare(Boolean(policy))}>{busy ? 'Preparing…' : policy ? 'Start new revision' : 'Prepare policy revision'}</button></div></div>
    {!policy ? <EmptyState title="The evidence is ready for review">Prepare a policy revision to review candidate removals. Every field starts with API KEEP.</EmptyState> : <>
      <div className="compact-stats"><div><span>API KEEP</span><strong>{policy.summary.api_actions.KEEP}</strong></div><div><span>API REMOVE</span><strong className="amber-text">{policy.summary.api_actions.REMOVE}</strong></div><div><span>Planned shape</span><strong>{policy.summary.fields_before} <span className="muted">→</span> {policy.summary.fields_after}</strong></div><div><span>Approval</span><strong className="text-value">{policy.approval?.reviewer || 'Not reviewed'}</strong></div></div>
      <div className="notice"><Icon name="lock" /><p>Only eligible review candidates can be selected. Log actions come from sensitivity and do not decide API removal. Approval is stored once for this revision.</p></div>
      <section className="panel"><div className="panel-toolbar"><div><h2>Review field actions</h2><p>Inspect the evidence before proposing a removal.</p></div><button className="text-button" disabled={!reviewable || busy || !candidates.length} onClick={() => { setSelected(selected.length === candidates.length ? [] : candidates.map(field => field.name)); setPreview(null) }}>{selected.length === candidates.length && candidates.length ? 'Clear selection' : 'Select all candidates'}</button></div><div className="table-scroll"><table><thead><tr><th className="checkbox-cell"><span className="sr-only">Removal selection</span></th><th>Field</th><th>Usage</th><th>Sensitivity</th><th>API action</th><th>Log action</th></tr></thead><tbody>{policy.fields.map(field => <tr key={field.name} className={selected.includes(field.name) ? 'selected-row' : ''}><td className="checkbox-cell"><input type="checkbox" aria-label={`Approve removal of ${field.name}`} disabled={!reviewable || busy || field.usage !== 'CANDIDATE_UNUSED' || !field.removal_allowed} checked={selected.includes(field.name)} onChange={event => { setSelected(values => event.target.checked ? [...values, field.name] : values.filter(value => value !== field.name)); setPreview(null) }} /></td><td><code className="field-name">{field.name}</code><details className="policy-evidence"><summary>Evidence</summary>{field.evidence.map((item, index) => <p key={index}>{item}</p>)}</details></td><td><UsageBadge usage={field.usage} /></td><td><span className="sensitivity">{field.sensitivity}</span></td><td><Badge tone={selected.includes(field.name) || field.api_action === 'REMOVE' ? 'candidate_unused' : 'neutral'}>{selected.includes(field.name) ? 'REMOVE proposed' : field.api_action}</Badge></td><td><Badge tone={field.log_action === 'DROP' ? 'drop' : 'neutral'}>{field.log_action}</Badge></td></tr>)}</tbody></table></div></section>
      {reviewable ? <section className="panel review-form"><div><h2>Record your decision</h2><p>This compiles the policy for future runtime requests. No API request is made by saving a review.</p></div><div className="form-grid"><label>Reviewer label <span className="required">required</span><input value={reviewer} onChange={event => { setReviewer(event.target.value); setPreview(null) }} placeholder="Your reviewer label" disabled={busy} maxLength={120} /></label><label>Review notes <span className="muted">optional</span><input value={notes} onChange={event => { setNotes(event.target.value); setPreview(null) }} placeholder="Why are these removals appropriate?" disabled={busy} maxLength={2000} /></label></div><div className="review-actions"><span>{selected.length} candidate{selected.length === 1 ? '' : 's'} selected for removal</span><div className="button-row"><button className="button secondary" onClick={() => setPreview('REJECT')} disabled={busy || !reviewer.trim()}>Review rejection</button><button className="button primary" onClick={() => setPreview('APPROVE')} disabled={busy || !reviewer.trim()}>Review approval <Icon name="arrow" size={16} /></button></div></div>{preview && <section className="confirmation" aria-label="Approval summary"><span className="eyebrow">CONFIRM THIS REVISION</span><h3>{preview === 'REJECT' ? 'Keep every field and record rejection' : `Approve ${selected.length} candidate removal${selected.length === 1 ? '' : 's'}`}</h3><p>Revision <code>{policy.revision.revision_id}</code> · Reviewer <strong>{reviewer.trim()}</strong></p><p>Planned API shape: <strong>{policy.fields.length} → {policy.fields.length - (preview === 'APPROVE' ? selected.length : 0)} fields</strong>. USED and UNKNOWN fields remain KEEP.</p>{preview === 'APPROVE' && selected.length > 0 && <div className="selection-list">{selected.map(name => <code key={name}>{name}</code>)}</div>}<div className="button-row"><button className="button primary" disabled={busy} onClick={submit}>{busy ? 'Saving…' : preview === 'REJECT' ? 'Confirm rejection' : 'Confirm approval'}</button><button className="button secondary" disabled={busy} onClick={() => setPreview(null)}>Back to selection</button></div></section>}</section> : <div className="notice"><Icon name="check" /><p>Decision recorded by <strong>{policy.approval?.reviewer}</strong>. This revision is immutable. Start a new revision to change the decision.</p></div>}
      <Warnings warnings={policy.warnings} />
      <div className="two-column"><section className="panel history-panel"><h2>Revision history</h2>{envelope.history.length ? [...envelope.history].reverse().map(revision => <div className="history-row" key={revision.revision_id}><code>{revision.revision_id}</code><Badge tone={revision.status === 'APPROVED' ? 'used' : 'neutral'}>{revision.status.replaceAll('_', ' ')}</Badge></div>) : <p>No revisions recorded.</p>}</section><details className="panel compiled-json"><summary>Compiled policy JSON <span className="mono">↗</span></summary><pre tabIndex={0}>{JSON.stringify(policy, null, 2)}</pre></details></div>
    </>}
  </>
}

function ApiView() {
  const [mode, setMode] = useState<Mode>('OBSERVE')
  const [result, setResult] = useState<ApiInspection | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setBusy(true); setError(null); setResult(null)
    try { setResult(await request<ApiInspection>(`/api/demo/account?mode=${mode}`)) }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <>
    <div className="inspector-controls"><div><span className="eyebrow">SYNTHETIC RESPONSE PATH</span><p>The server loads the latest policy. The client cannot supply one.</p></div><div className="button-row"><label className="mode-select">Runtime mode<select value={mode} onChange={event => { setMode(event.target.value as Mode); setResult(null) }} disabled={busy}>{(['OBSERVE', 'WARN', 'ENFORCE'] as Mode[]).map(value => <option key={value}>{value}</option>)}</select></label><button className="button primary" onClick={run} disabled={busy}>{busy ? 'Inspecting…' : 'Run synthetic response'}<Icon name="arrow" size={16} /></button></div></div>
    <div className="notice"><Icon name="shield" /><p>{mode === 'ENFORCE' ? 'ENFORCE applies only removals approved in the current valid revision. Missing, invalid, pending or stale policies retain the original response.' : `${mode} returns the original response. Proposed removals and policy warnings are recorded in the trace.`}</p></div>
    <ErrorMessage message={error} />
    {!result ? <EmptyState title={busy ? 'Inspecting the runtime path…' : 'No response inspected yet'}>Run the synthetic request to see the actual backend output and policy trace.</EmptyState> : <>
      <div className="result-strip"><div><span>Response shape</span><strong>{Object.keys(result.original).length} → {Object.keys(result.output).length} <small>fields</small></strong></div><div><span>Policy revision</span><code>{result.trace.policy_revision || 'Unavailable'}</code></div><Badge tone={result.trace.policy_valid ? 'used' : 'candidate_unused'}>{result.trace.policy_valid ? 'Valid approved policy' : 'Fail-safe: original retained'}</Badge><Badge>{result.trace.mode}</Badge></div>
      <div className="two-column"><JsonPanel title="Original synthetic response" value={result.original} /><JsonPanel title="Actual runtime output" value={result.output} accent note={Object.hasOwn(result.output, 'internal_risk_flag') ? 'UNKNOWN field internal_risk_flag remains in the API response.' : undefined} /></div>
      <div className="panel trace-panel"><h2>Internal enforcement trace</h2><div className="trace-grid"><div><span>Removed paths</span><code>{result.trace.removed_paths.length ? result.trace.removed_paths.join(', ') : 'None'}</code></div><div><span>Would remove</span><code>{result.trace.would_remove_paths.length ? result.trace.would_remove_paths.join(', ') : 'None'}</code></div></div><p className="muted">Trace metadata is separate from the customer response.</p></div><Warnings warnings={result.trace.warnings} />
    </>}
  </>
}

function LogsView() {
  const [result, setResult] = useState<LogInspection | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setBusy(true); setError(null); setResult(null)
    try { setResult(await request<LogInspection>('/api/demo/log', {})) }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <>
    <div className="inspector-controls"><div><span className="eyebrow">STRUCTURED EVENT → PROTECTION → SQLITE</span><p>Only the protected event reaches the log sink.</p></div><button className="button primary" onClick={run} disabled={busy}>{busy ? 'Protecting…' : 'Protect synthetic event'}<Icon name="arrow" size={16} /></button></div>
    <ErrorMessage message={error} />
    {!result ? <EmptyState title={busy ? 'Protecting and persisting…' : 'No protected event yet'}>Create a synthetic event to inspect sensitivity-based actions and the actual saved record.</EmptyState> : <>
      <div className="result-strip"><div><span>Protected record</span><strong>#{result.persisted.id}</strong></div><div><span>Policy revision</span><code>{result.persisted.policy_revision || 'Unavailable · mask-all fallback'}</code></div><Badge tone="used"><Icon name="lock" size={12} /> Sanitized before persistence</Badge></div>
      <div className="three-column"><JsonPanel title="Before protection · synthetic" value={result.original} /><JsonPanel title="After protection" value={result.sanitized} accent /><JsonPanel title="Persisted SQLite event" value={result.persisted.event} accent note={`Record ${result.persisted.id} · ${result.persisted.mode}`} /></div>
      <section className="panel"><div className="panel-toolbar"><div><h2>Applied log actions</h2><p>API usage never overrides log sensitivity.</p></div><span className="mono muted">{result.trace.actions.length} paths</span></div><div className="action-grid">{result.trace.actions.map((action, index) => <div className="action-row" key={index}><code>/{action.path.join('/')}</code><Badge tone={action.action === 'DROP' ? 'drop' : action.action === 'ALLOW' ? 'used' : 'neutral'}>{action.action}</Badge></div>)}</div></section><Warnings warnings={result.trace.warnings} />
    </>}
  </>
}

function CanaryView({ policy }: { policy: Policy | null }) {
  const [result, setResult] = useState<Verification | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setBusy(true); setError(null); setResult(null)
    try { setResult(await request<Verification>('/api/verify', { revision_id: policy?.revision.revision_id || null })) }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <>
    <section className="canary-intro panel"><div className="canary-icon"><Icon name="canary" size={31} /></div><div><span className="eyebrow">SYNTHETIC, PATH-SCOPED VERIFICATION</span><h2>Evidence from the paths that actually run.</h2><p>Fresh unique markers pass through API enforcement and structured log protection. The backend checks the returned response and the record persisted in SQLite.</p></div><button className="button primary" onClick={run} disabled={busy}>{busy ? 'Verifying…' : 'Run fresh verification'}<Icon name="arrow" size={16} /></button></section>
    <div className="notice"><Icon name="shield" /><p>This checks the defined synthetic paths and current policy revision. It does not establish complete security, compliance, or protection for untested integrations.</p></div>
    <ErrorMessage message={error} />
    {!result ? <EmptyState title={busy ? 'Checking actual runtime and storage…' : 'No verification run in this view'}>Run a fresh check. Previous PASS results are cleared before each run.</EmptyState> : <>
      <section className={`verification-result ${result.status.toLowerCase()}`} aria-label="Verification result"><div><span className="eyebrow">BACKEND VERIFICATION RESULT</span><h2>{result.status === 'PASS' ? 'Protected paths verified' : 'Verification found a failure'}</h2><p className="mono">{result.run_id}</p></div><Badge tone={result.status === 'PASS' ? 'used' : 'drop'}>{result.status}</Badge><div className="run-metadata"><span>Policy <code>{result.policy_revision || 'unavailable'}</code></span><span>Checked <time>{new Date(result.checked_at).toLocaleString()}</time></span></div></section>
      <section className="panel checks-panel"><h2>Verification evidence</h2>{result.checks.map((check, index) => <div className="check-row" key={index}><span className={`check-indicator ${check.passed ? 'pass' : 'fail'}`}>{check.passed ? <Icon name="check" size={15} /> : '×'}</span><div><strong>{check.name}</strong><p>{check.detail}</p></div><Badge tone={check.passed ? 'used' : 'drop'}>{check.passed ? 'PASS' : 'FAIL'}</Badge></div>)}</section>
      <div className="two-column"><JsonPanel title="Verified API output" value={result.api.output} accent /><JsonPanel title="Verified persisted log event" value={result.log.persisted.event} accent /></div><Warnings warnings={result.warnings} />
    </>}
  </>
}

function ExamplesView({review}: {review:()=>void}){
  const [tab,setTab]=useState<'api'|'logs'|'canary'>('api')
  const [policy,setPolicy]=useState<Policy|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{let active=true;void request<PolicyEnvelope>('/api/policy').then(r=>{if(active)setPolicy(r.policy)}).catch(()=>{if(active)setError('Example policy could not be loaded.')});return()=>{active=false}},[])
  return <><div className="notice"><p>The original synthetic ten-field example and its policy history are preserved. These results describe that example only.</p><button className="text-button" onClick={review}>Review example policy →</button></div><ErrorMessage message={error}/><div className="example-tabs">{(['api','logs','canary'] as const).map(key=><button className={'button '+(tab===key?'primary':'secondary')} key={key} onClick={()=>setTab(key)}>{key==='api'?'Example API':key==='logs'?'Example logs':'Example canary'}</button>)}</div>{tab==='api'?<ApiView/>:tab==='logs'?<LogsView/>:<CanaryView policy={policy}/>}</>
}

function Dashboard() {
  const [view,setView]=useState<View>('traffic')
  const [destination,setDestination]=useState<'bank'|'example'>('bank')
  const [analysis,setAnalysis]=useState<Analysis|null>(null)
  const [envelope,setEnvelope]=useState<PolicyEnvelope>({policy:null,history:[]})
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState<string|null>(null)
  const [refreshKey,setRefreshKey]=useState(0)
  useEffect(()=>{let active=true;setLoading(true);setError(null)
    const analysisPath=destination==='bank'?'/api/bank-analysis':'/api/analysis'
    const policyPath=destination==='bank'?'/api/bank-policy':'/api/policy'
    void Promise.all([request<Analysis>(analysisPath),request<PolicyEnvelope>(policyPath)]).then(([a,p])=>{if(active){setAnalysis(a);setEnvelope(p)}}).catch(reason=>{if(active)setError((reason as Error).message)}).finally(()=>{if(active)setLoading(false)})
    return()=>{active=false}
  },[destination,refreshKey])
  const chooseDestination=(value:'bank'|'example')=>{setAnalysis(null);setEnvelope({policy:null,history:[]});setDestination(value)}
  const navigation:[View,string][]=[['flow','Data Flow Explorer'],['traffic','Live bank traffic'],['accounts','Accounts Explorer'],['evidence','Field evidence'],['policy','Policy review'],['inspector','Protection inspector']]
  useEffect(()=>{const open=()=>setView('flow');window.addEventListener('veilmint:open-flow',open);return()=>window.removeEventListener('veilmint:open-flow',open)},[])
  const current=envelope.policy
  return <div className="app-shell">
    <aside className="sidebar"><a href="#main" className="brand" aria-label="VEILMINT workbench"><span className="brand-mark"><Icon name="shield" size={25}/></span><span>VEILMINT<small>LEAST DATA. MORE CERTAINTY.</small></span></a><div className="workspace-switch"><span className="workspace-avatar">N</span><div><strong>NEXUS BANK</strong><span>Operator workspace</span></div></div><span className="nav-label">WORKBENCH</span><nav aria-label="Workbench navigation">{navigation.map(([key,label],index)=><button key={key} className={view===key?'nav-item active':'nav-item'} aria-current={view===key?'page':undefined} onClick={()=>setView(key)}><Icon name={key}/><span>{label}</span><small aria-hidden="true">{String(index+1).padStart(2,'0')}</small></button>)}<div className="nav-group-label">ORIGINAL FIXTURE</div><button className={view==='examples'?'nav-item active':'nav-item'} onClick={()=>setView('examples')} aria-current={view==='examples'?'page':undefined}><Icon name="examples"/><span>Demo examples</span></button></nav><div className="sidebar-bottom"><div className="local-note"><Icon name="lock" size={15}/><span>Local & synthetic</span></div><p>Read-only source inspection.<br/>Explicit policy decisions.</p><div className="sidebar-version"><span>VEILMINT WORKBENCH</span><code>v0.9</code></div></div></aside>
    <div className="main-shell"><header className="topbar"><div><span className="breadcrumb">Workspace <span>/</span> NEXUS BANK</span><strong>Data Flow Security Console</strong></div><div className="topbar-right"><Badge><span className="dot"/>Synthetic sandbox</Badge><span className="local-tag">LOCAL OPERATOR</span></div></header><main id="main" className="main-content"><DashboardModeToggle/><CloudHostStatus/><div className="page-heading"><div><span className="eyebrow">NEXUS BANK / SECURITY OPERATIONS</span><h1>{titles[view][0]}</h1><p>{titles[view][1]}</p></div><button className="button secondary refresh-button" onClick={()=>setRefreshKey(v=>v+1)} disabled={loading}><Icon name="refresh" size={15}/>{loading?'Refreshing…':'Refresh workspace'}</button></div>
    {['evidence','policy'].includes(view)&&<div className="destination-selector"><label>Policy destination<select aria-label="Policy destination" value={destination} onChange={e=>chooseDestination(e.target.value as 'bank'|'example')}><option value="bank">NEXUS BANK · account summary</option><option value="example">Original golden example · demo only</option></select></label><p>{destination==='bank'?'Explicit endpoint contract; TypeScript has not been statically analyzed.':'Original Python-consumer fixture; approvals are separate from the bank endpoint.'}</p></div>}
    <ErrorMessage message={error}/>{loading?<div className="loading-state" role="status"><h2>Loading evidence and policy…</h2><p>Reading the selected destination from the backend.</p></div>:!analysis?<EmptyState title="The workspace is unavailable">Start the backend and refresh to load the current state.</EmptyState>:<div className="view-content" key={`${view}-${destination}-${current?.revision.revision_id}-${current?.revision.status}`}>
      {view==='flow'&&<ConsumerLab/>}{view==='traffic'&&<LiveTraffic/>}{view==='accounts'&&<AccountsExplorer/>}{view==='inspector'&&<AccountsExplorer inspection/>}
      {view==='evidence'&&<EvidenceView analysis={analysis} goReview={()=>setView('policy')}/>}
      {view==='policy'&&<PolicyView envelope={envelope} onChange={setEnvelope} endpoint={destination==='bank'?'/api/bank-policy':'/api/policy'}/>}
      {view==='examples'&&<ExamplesView review={()=>{chooseDestination('example');setView('policy')}}/>}
    </div>}<footer className="main-footer"><span>VEILMINT / Evidence-Compiled Least-Data Firewall</span><span>{['policy','evidence'].includes(view)?`${destination==='bank'?'Bank':'Example'} review context · ${current?'revision '+current.revision.number:'no revision'}`:'Actual bank records and explicit protection evidence'}</span></footer></main></div>
  </div>
}

export default function App(){return <DashboardModeProvider><Dashboard/></DashboardModeProvider>}
