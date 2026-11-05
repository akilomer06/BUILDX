# GitHub + Vercel frontend + Render Free demo backend

Vercel project root is **frontend/**. `frontend/vercel.json` builds the Vite app,
routes SPA pages and sends /api through the server-only Node proxy. Never place
an operator token in VITE_* variables or browser code.

The current Python bank uses SQLite files for ledger, sessions and independent
policy histories. Vercel function filesystems do not provide the required shared
persistent storage. The prepared `render.yaml` explicitly selects **plan: free**
and has **no disk or paid database**. SQLite lives in the container's ephemeral
`/data` directory. Accounts, balances, transactions, sessions, traffic and policy
history are lost on sleep, restart or redeploy. This is a disposable fictional
demo, not durable bank hosting. Local laptop databases remain unchanged.

Render Free sleeps after 15 idle minutes and waking can take about a minute.
Open the Render backend `/ready` URL first and wait for it to become healthy
before demonstrating the Vercel app; retry any first request that times out.
Free instance-hour and bandwidth/build limits still apply. Do not add a payment
method, upgrade the service, or attach paid storage for this setup.
See [Render Free limitations](https://render.com/docs/free).

1. Push this repository and deploy frontend/ on Vercel.
2. In Render, create a Blueprint from this repository and confirm the web service
   instance type says **Free** with no disk or database. Set the backend
   VEILMINT_OPERATOR_TOKEN to the new cloud token in the local ignored .env.cloud
   file. The blueprint generates its separate HMAC key and enables HTTPS cookies.
   The cloud database starts empty on every fresh instance; local SQLite files
   are never uploaded. Recreate fictional demo users after a reset.
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
   bank deployment until the backend is actually connected.

The Render entrypoint initializes ephemeral data ownership, drops root privileges
and launches the existing FastAPI factory. Render Free does not offer a service
shell or SSH; any CLI-only funding must be prepared separately before a cloud
demonstration. No HTTP funding route is introduced. Raw credentials, .env files,
.vercel state, databases, QA artifacts
and node_modules must not be committed.

After connection: register fictional bank customers, refresh the operator traffic
response, and review consumer policies before testing minimization. New cloud
policies start pending. Transfers need a funded sandbox account; a fresh cloud
instance has no funded accounts by default.
