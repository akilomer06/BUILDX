# Implementation coverage

Statuses refer to bounded evidence, not every possible production deployment.

| Requirement / phase | Source plan | Actual implementation | Tests / evidence | State |
|---|---|---|---|---|
| Phase 1 golden 5/4/1, schema validation, conservative AST | Final PDF; Phase 1 prompts | analyzer/, fixtures/ | schema_inventory, ast_analyzer, report test suites | VERIFIED |
| Phase 2 human revisions/compiler, immutable reviews | Phase 2 prompt | policy/compiler.py, store.py, cli.py | policy compiler/store tests, stale/USED rejection | VERIFIED |
| Phase 3 API observe/warn/enforce, uncertainty | Phase 3 prompt | runtime/api.py | test_runtime_api.py, consumer pending/mode tests | VERIFIED |
| Phase 4 log sanitize before persist | Phase 4 prompt | runtime/logs.py | log sanitizer/sink tests, correlated consumer canaries | VERIFIED |
| Phase 5 canaries and actual sinks | Phase 5 prompt | verification.py, consumer_lab.verify | golden and consumer tests | VERIFIED within tested paths |
| Phase 6 frontend/FastAPI/Docker | Phase 6 prompt | server.py, frontend/, compose.yaml, nginx | typecheck/build/frontend/HTTP checks | VERIFIED functionally; visual NOT TESTED |
| Phase 7 | No accessible prompt | Prior records postpone it | No invented requirements | NOT FOUND / NOT IMPLEMENTED |
| Phase 8 real bank, LAN split, persistence | Phase 8 prompt | bank/, routes/service/CLI, nginx.customer.conf | bank/operator tests, real HTTP UI flow | VERIFIED locally; physical LAN NOT TESTED |
| Numeric INR migration and Accounts Explorer | amendments/docs | bank/service.py, explorer.py | numeric INR and operator explorer tests | VERIFIED |
| Live HTTP/JSON modal and masking | response-view amendments | response_inspection.py, ResponseInspector.tsx | 27 baseline frontend tests; HTTP workflow | VERIFIED functionally; visual NOT TESTED |
| Phase 9 A audit and baseline | Phase 9 | docs/audit/* | recorded command outputs and plan inventory | IMPLEMENTED |
| Phase 9 B rich canonical producer | Phase 9 | nexus_demo_producer, ConsumerLab.producer/seed | canonical persistence/idempotency/ledger tests | VERIFIED for explicit DEMO enrichment |
| Phase 9 C four real logical consumers | Phase 9 | consumers/*.py, consumer_lab.py | four distinct approved field sets; actual functions executed | VERIFIED |
| Phase 9 D baseline/protected comparison | Phase 9 | ConsumerLab trace; ConsumerLab.tsx | frozen source version, byte counts, actual mode, toggle tests | VERIFIED |
| Phase 9 E security console | Phase 9 | Data Flow Explorer, existing PolicyView reused, consumerLab.css | frontend integration and baseline regression tests | IMPLEMENTED; visual NOT TESTED |
| Phase 9 F lineage/schema drift | Phase 9 | digest-bound reports, per-field evidence, unknown warnings | stale/unknown/USED tests | VERIFIED; no nested static proof claimed |
| Phase 9 G selected upgrades | Phase 9 | canaries and same-source matrix | tests and execution measurements | IMPLEMENTED |
| Independently deployed microservices | Phase 9 optional | Not deployed separately | Explicit in-process label | SUPERSEDED WITH EXPLANATION |
| Nested schema/array AST proof | Phase 9 audit item; original PDF top-level scope | Runtime supports paths; AST remains top-level | runtime nested tests, scope warnings | PARTIAL |
| Multi-account populated sandbox | Phase 9 | existing registration/fund/transfer flows, seed per chosen account | original real HTTP banking tests | VERIFIED; no silent seeded transactions |

## Accessible source-plan inventory

- `C:\Users\brain\Downloads\VEILMINT_Phase_1_Fresh_Start.md` — SHA256 `b59d0c30e8818effd7ed0ce1e930348edf0c338c0133897a37ab070775c07d1e`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_1_Master_Prompt_NoTime.md` — SHA256 `94daba89b70dc424eb12cf6d1bec4990f80d33e5d7789db778f92302c12affad`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_2_Master_Prompt-1.md` — SHA256 `52fce9e362873f2fcf5da26e1fcdb80105ebf7462861a939cc6d4c7984df201f`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_3_Master_Prompt.md` — SHA256 `55e3a83364fc5dfd2bff1f0ba1c9326818a0937814136771fa66affe44cb5475`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_4_Master_Prompt.md` — SHA256 `777e950c85e5152254462724040ff260d8389c75c115d15c0af17ed775a81392`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_5_Master_Prompt.md` — SHA256 `7190b31acf92e711148e2a4fc5b4fcbb6168a5dc90b2a98e96d8e3b9906bcff2`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_6_Master_Prompt.md` — SHA256 `95867c8e5ed279ce588336404242ee41bde21b378a7face702c4dcab473a63a7`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_8_Master_Prompt.md` — SHA256 `037560c6b8aa006f31e2e9897025ea72da8356c4a11e97aca3ebbcf1df752494`; full text read.

- `C:\Users\brain\Downloads\VEILMINT_Phase_9_Audit_Upgrade_Master_Prompt.md` — SHA256 `f11b987005e9ebe09ae5626b3526955b0db96e63a7006692f089455a80bf7f0f`; full text read.

- `docs\api.md` — SHA256 `bf429f11c3954df704b250a1751680ea84db1ed991c96a2b214104ba92cd1cae`; full text read.

- `docs\deployment.md` — SHA256 `78bd30bbe3019466554fc25fe5777296a9cb0ed8336e79ed4f5377060e38891c`; full text read.

- `docs\operator-inspection.md` — SHA256 `cd37160fa8d4c77fbad5cc2418d23337b41b04c9506492c19f1aabc0614322c8`; full text read.

- `docs\phase8-verification.md` — SHA256 `d3f4f5612ed6f97683a2db4118c96e842eaf0ce298244acdf1c3b3b210077a3a`; full text read.

- `docs\phase8.md` — SHA256 `a52e0940da5005b2c994f0481bd901783eab3ac0e12ab6b0dfd99a06f330f8b0`; full text read.

- `docs\traffic-responses.md` — SHA256 `92b3baf7590bee6b341ed3ca82c184cc3d35422fb79e5660638e33bc4a840389`; full text read.

- `docs\verification.md` — SHA256 `afb03df218909975c029713bf1a0815e7cfe9697b18df8c4a7d4fc63d309808b`; full text read.

- `prompts\VEILMINT_Phase_1_Fresh_Start.md` — SHA256 `b59d0c30e8818effd7ed0ce1e930348edf0c338c0133897a37ab070775c07d1e`; full text read.

- `prompts\VEILMINT_Phase_1_Master_Prompt_NoTime.md` — SHA256 `94daba89b70dc424eb12cf6d1bec4990f80d33e5d7789db778f92302c12affad`; full text read.

- `prompts\VEILMINT_Phase_2_Master_Prompt-1.md` — SHA256 `52fce9e362873f2fcf5da26e1fcdb80105ebf7462861a939cc6d4c7984df201f`; full text read.

- `prompts\VEILMINT_Phase_3_Master_Prompt.md` — SHA256 `55e3a83364fc5dfd2bff1f0ba1c9326818a0937814136771fa66affe44cb5475`; full text read.

- `prompts\VEILMINT_Phase_4_Master_Prompt.md` — SHA256 `777e950c85e5152254462724040ff260d8389c75c115d15c0af17ed775a81392`; full text read.

- `prompts\VEILMINT_Phase_5_Master_Prompt.md` — SHA256 `7190b31acf92e711148e2a4fc5b4fcbb6168a5dc90b2a98e96d8e3b9906bcff2`; full text read.

- `prompts\VEILMINT_Phase_6_Master_Prompt.md` — SHA256 `95867c8e5ed279ce588336404242ee41bde21b378a7face702c4dcab473a63a7`; full text read.

Final PDF full text extracted to ignored data/phase9-final-plan-extracted.txt; requirements inspected. Missing Phase 7 explicitly recorded.
