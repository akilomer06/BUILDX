export type Usage = 'USED' | 'CANDIDATE_UNUSED' | 'UNKNOWN'
export type Sensitivity = 'GENERAL' | 'INTERNAL' | 'MEDIUM' | 'FINANCIAL' | 'HIGH'
export type LogAction = 'ALLOW' | 'MASK' | 'DROP' | 'HMAC_PSEUDONYM'
export type Mode = 'OBSERVE' | 'WARN' | 'ENFORCE'
export type JsonObject = Record<string, unknown>

export interface FieldEvidence {
  name: string
  usage: Usage
  sensitivity: Sensitivity
  evidence: string[]
}
export interface Analysis {
  fields: FieldEvidence[]
  counts: Record<Usage, number>
  warnings: string[]
  analysis: { mode?: string; consumer: string; root_name: string; scope: string; limitations: string[] }
  schema_validation: { schema_valid: boolean; payload_valid: boolean }
}
export interface Revision {
  revision_id: string
  number: number
  analysis_digest: string
  inputs_digest: string
  created_at: string
  status: 'REVIEW_REQUIRED' | 'APPROVED' | 'REJECTED'
}
export interface FieldPolicy extends FieldEvidence {
  api_action: 'KEEP' | 'REMOVE'
  log_action: LogAction
  path: string[]
  removal_allowed: boolean
}
export interface Policy {
  revision: Revision
  fields: FieldPolicy[]
  warnings: string[]
  approval: null | {
    reviewer: string; notes: string; approved_fields: string[]; decided_at: string; decision: 'APPROVE' | 'REJECT'
  }
  summary: {
    fields_before: number; fields_after: number; fields_removed: number
    api_actions: Record<'KEEP' | 'REMOVE', number>
    log_actions: Record<LogAction, number>
  }
}
export interface PolicyEnvelope { policy: Policy | null; history: Revision[]; synthetic?: boolean }
export interface Trace {
  mode: Mode; policy_revision: string | null; policy_valid: boolean
  warnings: string[]; removed_paths: string[]; would_remove_paths: string[]
}
export interface ApiInspection { synthetic: boolean; original: JsonObject; output: JsonObject; trace: Trace }
export interface PersistedLog { id: number; event: JsonObject; policy_revision: string | null; mode: string; created_at: string }
export interface LogInspection {
  synthetic: boolean; original: JsonObject; sanitized: JsonObject; persisted: PersistedLog
  trace: { policy_revision: string | null; warnings: string[]; actions: { path: (string | number)[]; action: LogAction }[] }
}
export interface Verification {
  run_id: string; checked_at: string; status: 'PASS' | 'FAIL'; synthetic: boolean
  scope: string; policy_revision: string | null
  checks: { name: string; passed: boolean; detail: string }[]
  api: { original: JsonObject; output: JsonObject; trace: Trace }
  log: { sanitized: JsonObject; persisted: PersistedLog }
  warnings: string[]
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
  } catch {
    throw new Error('The local backend is unavailable. Check that it is running, then try again.')
  }
  if (!response.ok) {
    if (response.status === 409) throw new Error('The policy revision changed or was already reviewed. Refresh before continuing.')
    if (response.status === 422) throw new Error('The request could not be validated. Check the reviewer and selected candidates.')
    throw new Error('The backend could not complete this operation. No success has been assumed; refresh and try again.')
  }
  try { return await response.json() as T }
  catch { throw new Error('The backend returned an unreadable result. Try refreshing the workspace.') }
}
