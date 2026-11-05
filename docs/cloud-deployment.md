# GitHub + Vercel frontend + persistent backend

Vercel project root is **frontend/**. `frontend/vercel.json` builds the Vite app,
routes SPA pages and sends /api through the server-only Node proxy. Never place
an operator token in VITE_* variables or browser code.

The current Python bank uses SQLite files for ledger, sessions and independent
policy histories. Vercel function filesystems do not provide the required shared
persistent storage. The prepared `render.yaml` deploys this existing backend with
a 1 GiB disk and one service instance. **Render's starter service and persistent
disk are paid resources. The blueprint is preparation, not authorization to
purchase them; review the provider's pricing before creating that service.**

1. Push this repository and deploy frontend/ on Vercel.
2. Connect the repository in Render and review the blueprint. Set the backend
   VEILMINT_OPERATOR_TOKEN to the new cloud token in the local ignored .env.cloud
   file. The blueprint generates its separate HMAC key and enables HTTPS cookies.
   The cloud database starts empty; local SQLite files are never uploaded.
3. When Render reports /ready healthy, set Vercel BACKEND_URL to its HTTPS origin
   (no path/query), and redeploy the Vercel project.
4. Set Vercel CLOUD_OPERATOR_USERNAME, CLOUD_OPERATOR_PASSWORD and
   VEILMINT_OPERATOR_TOKEN server variables. The backend token must match Render.
   New cloud-only values can be saved in .env.cloud, which is ignored by Git.
5. Visit `/api/cloud-login` on the Vercel URL for browser operator sign-in. This
   password protects operator API access. Customer /bank/ routes retain their
   own bank login. The proxy never forwards browser Basic credentials or caller
   operator headers. It validates browser origins before forwarding requests.
6. Visit `/api/deployment-status` to check configuration booleans without exposing
   any secret. Until BACKEND_URL is configured, APIs deliberately return 503,
   and the hosted dashboard identifies the pending setup. This is not a working
   bank deployment until the persistent backend is actually connected.

The Render entrypoint initializes disk ownership, drops root privileges and
launches the existing FastAPI factory. Back up the cloud disk before migrations.
Use the backend shell/CLI for explicit sandbox funding; no HTTP funding route is
introduced. Raw credentials, .env files, .vercel state, databases, QA artifacts
and node_modules must not be committed.

After connection: register two fictional bank customers, explicitly fund one,
test transfer/idempotency, refresh the operator traffic response, and review
consumer policies before testing minimization. New cloud policies start pending.
