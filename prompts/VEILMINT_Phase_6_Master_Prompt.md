# VEILMINT — Phase 6 Master Prompt
## Deployment + Reproducible Demo Environment

You are continuing VEILMINT after Phases 1–5. Deploy the existing MVP and make the demo reproducible. Do not add product features or redesign the architecture.

## Starting Rule
Inspect the repository, read its setup/deployment documentation, and run existing tests/build checks. Verify the Phase 5 hardening results. Do not assume the app is deployable or tests pass. Preserve working code and report actual findings.

## Objective
Provide a reliable way to run VEILMINT locally and, if feasible with the project's constraints, a publicly accessible demo deployment using synthetic data only.

## 1. Deployment Strategy
- Prefer the simplest deployment path supported by the current repository.
- Keep backend and frontend deployment configuration minimal.
- If a public deployment is unsuitable (SQLite persistence limitations, platform filesystem behavior, secrets, or time constraints), deliver a polished local Docker Compose setup instead and explain why.
- Do not introduce cloud services or paid infrastructure without explicit approval.
- Never use real customer data.

## 2. Containerization
If Docker is available/appropriate:
- Create a backend Dockerfile.
- Create a frontend Dockerfile or production static build serving configuration.
- Create a Docker Compose file for the full application.
- Use health checks where practical.
- Persist SQLite in a clearly defined volume/path.
- Ensure containers start in the correct order and handle backend readiness.
- Pin or constrain dependencies sufficiently for reproducible builds.
- Do not bake secrets into images or commit `.env` files containing secrets.

If Docker is not available in the environment, still create and document the configuration, but do not claim it was built or tested.

## 3. Configuration and Secrets
- Provide `.env.example` with safe placeholder values and explanations.
- Keep HMAC secret external to source control.
- Define safe development defaults.
- Validate required configuration at startup.
- Never print secrets or sensitive payloads in startup logs.
- Clearly distinguish demo configuration from production configuration.

## 4. Synthetic Demo Initialization
- Provide a documented command/script to initialize the synthetic NEXUS BANK scenario and approved policy.
- Make initialization deterministic and idempotent.
- Never overwrite unrelated or non-demo database data.
- Clearly label all seeded records as synthetic.
- Ensure a fresh environment can reproduce the complete workflow.

## 5. Local Run and Optional Public Demo
Document exact commands for:
- installing dependencies;
- configuring environment;
- starting backend and frontend;
- starting with Docker Compose;
- initializing synthetic demo data;
- running tests and health checks.

If a public deployment is attempted:
- use only synthetic data;
- use supported hosting and persistent storage;
- configure secrets through host settings;
- verify deployed health and demo flow before claiming success;
- avoid exposing debug mode, raw payloads, database files, or administrative routes.

## 6. Deployment Verification
- Test clean startup and shutdown.
- Test health endpoints.
- Verify frontend can reach backend.
- Verify SQLite persistence across container restart if using Docker.
- Verify policy revision and approval survive restart.
- Verify API enforcement and log protection remain active after restart.
- Run the canary after startup and show fresh results.
- Document platform limitations and any unverified steps.

## Exclusions
Do not add authentication/RBAC, multi-tenancy, production customer integrations, complex orchestration, or paid infrastructure without approval. Do not claim production readiness or security certification.

## Completion Gate
Phase 6 is complete when:
- a clean environment can start VEILMINT using documented steps;
- configuration and secrets are handled safely;
- synthetic demo data can be initialized reproducibly;
- backend/frontend connectivity works;
- persistence and runtime protection survive restart;
- health and canary checks pass with actual results;
- deployment/build status is reported honestly.

At completion, provide:
1. deployment files created;
2. exact local/Docker commands;
3. actual build/test/deployment results;
4. demo initialization steps;
5. known limitations and whether a public deployment was truly verified.

**Stop after Phase 6. Do not begin presentation preparation.**
