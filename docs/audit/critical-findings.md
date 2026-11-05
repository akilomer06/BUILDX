# Findings and fixes

| Priority | Finding / reproduction | Root cause | Status / evidence |
|---|---|---|---|
| Critical demo correctness | Captured response shows nine customer DTO fields, not rich upstream record | Capture occurred after DTO construction and existing bank enforcement; database was not overwritten | FIXED in controlled consumer scenarios: persistent opt-in canonical enrichment and pre-enforcement baseline |
| High | No distinct downstream consumers | Single maintained account contract | FIXED: four real Python handlers, AST reports and separate policy databases; test_consumer_lab.py |
| High | Ad hoc display masking could be mistaken for approved minimization | Response inspector applies identifier rules to a served DTO | SCOPE CLARIFIED: live viewer remains served-body inspection; Data Flow Explorer demonstrates actual approved APIEnforcer removal, showing actual runtime mode |
| High | Automatic approvals would invalidate evidence | Tempting to preset removal policies | PREVENTED: new policies begin pending; existing reviewer/digest binding reused; no live candidate approval created by implementation |
| Medium | Field analysis is top-level | Original MVP analyzer intentionally does not prove nested Python field usage | LIMITATION: keep nested container whole if USED; runtime path enforcement and emitted leaf metrics work; do not claim leaf-level AST proof |
| Medium | Service impersonation on public routes | Consumer choice must not grant privilege | VERIFIED: operator middleware and customer proxy block invocation; no public service/header bypass. Separate workload credentials deferred until separate deployments exist |
| Medium | UI could retain an old consumer result | Asynchronous scenario requests | FIXED: results gated by account, consumer and actual runtime mode; selection clears obsolete results |
| Medium | Policy may change between enforcement and trace assembly | Independent store reads | FIXED: decisions load the exact enforced revision ID |
| Medium | Manual visual acceptance unavailable | Work settings disable browser control | NOT VERIFIED; reproducible walkthrough in phase9-end-to-end.md |

No claims of production RBAC, legal compliance, trained AI classification or universal leak absence are made. Canonical DEMO storage is local trusted SQLite, not encrypted enterprise PII storage.
