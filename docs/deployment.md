# Reproducible local demo

Phase 8 extends this setup with a separate customer proxy and a required private
operator proxy credential. Run `python scripts/configure_bank.py` before Compose.
See [the current bank/LAN guide](phase8.md) for customer sessions, funding,
endpoint-specific review and real traffic. Operator port 8080 stays host-only;
customer port 8081 is host-only until explicitly enabled for a trusted LAN.

This is a local, synthetic-only application. Public hosting was not attempted:
the local SQLite write model and unauthenticated reviewer/demo endpoints are
unsuitable for public exposure. No paid services or cloud resources were used.

## Native setup

Requires Python 3.12+ and Node 24 (the verified environment used Python 3.14).
From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m veilmint demo init --approve-synthetic
.\.venv\Scripts\python.exe -m veilmint demo check
.\.venv\Scripts\python.exe -m uvicorn veilmint.server:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The frontend proxies backend requests, so no CORS
configuration is needed. API mode defaults to OBSERVE. Choose ENFORCE in the
inspector, or set `$env:VEILMINT_MODE='ENFORCE'` before starting the backend.
For an unapproved review story omit `--approve-synthetic` and approve in the UI.
The flag deliberately records a synthetic initializer label, never a human identity.

Initialization is idempotent and never deletes records or overwrites decisions.
It refuses unrelated databases or mismatched analysis. For a clean demo choose
a new explicitly named file with `--db data/fresh-synthetic.sqlite3`, then set
`VEILMINT_DB` to the same path. Do not delete a database to reset the demo.
Run `demo check --db PATH` for fresh checks; each run creates a new canary ID.

## Docker Compose

Docker Desktop is installed and its Linux engine is running. Both image builds,
container health, Nginx-to-backend connectivity, the golden 10→6 response,
protected log readback and fresh canaries have been verified. Approval and
runtime protection also survived a restart of both containers using the named
SQLite volume. The tested workbench is at http://127.0.0.1:8080.

```powershell
python scripts/configure_bank.py
docker compose build
docker compose up -d
docker compose exec backend python -m veilmint demo init --db /data/synthetic-demo.sqlite3 --approve-synthetic
docker compose exec backend python -m veilmint demo check --db /data/synthetic-demo.sqlite3
docker compose ps
```

Open http://127.0.0.1:8080 for the operator and http://127.0.0.1:8081/bank/ for
customers. To verify persistence on a Docker-enabled machine:

```powershell
docker compose restart
docker compose exec backend python -m veilmint demo check --db /data/synthetic-demo.sqlite3
docker compose down
```

`demo-data` preserves SQLite and the bank's destination policy files across restart/down. Do not use `down -v` unless
you deliberately want to destroy that named volume. The two frontend ports are
published, bound to loopback by default. The backend uses a non-root user. Nginx proxies
`/api/` to the backend, serves the built frontend and has a backend health check.
Before initialization the workbench opens without a policy; no API minimisation
occurs. Startup rejects invalid modes and short configured HMAC secrets.

Images constrain Python/Node/Nginx versions, npm uses its exact lockfile and
Python dependencies are pinned in requirements-lock.txt. Base image tags are
not digest-pinned. Linux/amd64 container builds were verified; other architectures
remain unverified.

## Configuration and checks

Copy `.env.example` only for Compose. Native Python reads the process environment.
HMAC requires an external secret of at least 32 bytes and a configured mapping;
the golden mapping needs no key. Generate a key locally with
`python -c "import secrets; print(secrets.token_hex(32))"` and store it outside Git.
Do not put secrets in frontend Vite variables, images, logs or committed files.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
cd frontend
npm run typecheck
npm test
npm run build
npm audit
```

`/health` on the backend is liveness; `/ready` verifies database initialization
and write-transaction availability. Container/proxy health checks now use readiness.
Health does not imply an approved policy. `demo check` verifies original golden
approval/runtime paths; bank integration tests independently verify customer paths.
Stop native servers using Ctrl+C. There is no production authentication, public
deployment, complete security claim or compliance certification.
