# Ranked improvements and delivery

| Rank | Improvement | Security / demo value | Fit / risk | Definition of done | Delivery |
|---|---|---|---|---|---|
| 1 | Per-consumer lineage and drift binding | High: explains every removal and prevents stale approval reuse | Existing AST/compiler, bounded changes | Four reports, source lines, independent reviews, runtime tests | IMPLEMENTED |
| 2 | Per-consumer real canaries | High: proves candidate removal and HIGH log DROP independently | Shared engine and log sink | Correlated persisted result; no PASS on pending policy | IMPLEMENTED |
| 3 | Same-source comparison matrix | High demo correctness | Existing account read transactions; reject drift during matrix | Four executed consumers, equal source hashes | IMPLEMENTED |
| 4 | Separate workload identity infrastructure | Valuable for future independent services | Adds credentials/rotation complexity without separate deployments | Real service accounts and per-service transport auth | DEFERRED: current operator dispatch remains private and authenticated |
| 5 | Nested AST usage proof | Valuable deeper minimization | High regression risk; requires alias/dataflow semantics | Conservative nested paths with unknown propagation | DEFERRED: current top-level scope explicit, USED containers preserved |
| 6 | Runtime access instrumentation | Supporting evidence only | Avoid confusing non-observation with unused | Consent-controlled observed paths | DEFERRED: static evidence adequate for four explicit adapters |
| 7 | Automated contextual AI sensitivity | No proven need | Unverified model would weaken defensibility | Measured dataset/evaluation | NOT ADDED |

Continuous review in this task means repeated implementation/test/repair cycles. No unattended scheduled job or perpetual approval system was created.
