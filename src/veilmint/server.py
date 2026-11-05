"""Synthetic-only HTTP demo; core policy logic stays in reusable components."""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
import secrets
import time
from uuid import uuid4
from urllib.parse import urlsplit

from .config import Settings
from .demo import golden_analysis, golden_log_event, golden_payload
from .policy.compiler import analysis_digest
from .policy.store import PolicyStore, PolicyStoreError
from .runtime.api import APIEnforcer, RuntimeMode
from .runtime.logs import LogSink, StructuredLogPipeline
from .verification import verify_paths


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    new_revision: bool = False


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision_id: str = Field(min_length=1, max_length=128)
    analysis_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1, max_length=120)
    approved_fields: list[str] = Field(max_length=256)
    notes: str = Field(default="", max_length=2000)
    decision: Literal["APPROVE", "REJECT"] = "APPROVE"


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision_id: str | None = Field(default=None, max_length=128)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="VEILMINT · NEXUS BANK sandbox", version="0.8.0")
    app.state.settings = settings
    from .bank.routes import router as bank_router
    from .bank.service import BankError
    from .bank.protection import BankProtection, account_report, header_decisions
    app.include_router(bank_router(settings))
    from .consumer_lab import router as consumer_lab_router
    app.include_router(consumer_lab_router(settings,ReviewRequest))
    from .response_inspection import ResponseSnapshots, capture_response, router as response_router
    snapshots=ResponseSnapshots()
    app.state.response_snapshots=snapshots
    if settings.response_inspection_demo:
        app.include_router(response_router(snapshots))

    @app.exception_handler(BankError)
    async def bank_error(_request:Request,exc:BankError):
        body=capture_response(_request,{'detail':str(exc)},exc.status)
        return JSONResponse(status_code=exc.status,content=body)

    @app.middleware("http")
    async def safe_errors(request: Request, call_next):
        # Catch at the service boundary: an Exception handler alone is re-raised
        # by ASGI error middleware and may be logged with its original values.
        bank_request=request.url.path.startswith('/api/bank/')
        correlation=str(uuid4())
        started=time.perf_counter()
        request.state.correlation_id=correlation
        try:
            if request.url.path.startswith('/api/') and not bank_request:
                token=request.headers.get('x-veilmint-operator','')
                allowed=(secrets.compare_digest(token,settings.operator_token) if settings.operator_token
                         else request.client is not None and request.client.host in ('127.0.0.1','::1','testclient'))
                if not allowed:
                    return JSONResponse(status_code=403,content={'detail':'Operator access required.'})
                if request.headers.get('origin') and urlsplit(request.headers['origin']).netloc!=request.headers.get('host'):
                    return JSONResponse(status_code=403,content={'detail':'Operator request origin rejected.'})
            if bank_request and request.method not in ('GET','HEAD','OPTIONS') and (
                request.headers.get('x-nexus-request')!='1'
                or request.headers.get('origin') and urlsplit(request.headers['origin']).netloc!=request.headers.get('host')
            ):
                response=JSONResponse(status_code=403,content={'detail':'Invalid request origin.'})
            else:
                response = await call_next(request)
        except Exception:
            response=JSONResponse(status_code=503,content={'detail':'Operation unavailable; retry transfers with the same idempotency key.'})
        if bank_request:
            route=request.scope.get('route')
            endpoint=getattr(route,'path','/api/bank/unmatched')
            protection=getattr(request.state,'protection',None)
            metadata={
                'event_type':endpoint.replace('/api/bank/','').replace('/','.'),
                'endpoint':endpoint,'method':request.method,'http_status':response.status_code,
                'correlation_id':correlation,'destination':getattr(request.state,'destination','nexus_bank.unprotected_route'),
                'policy_revision':protection.policy_revision if protection else None,
                'mode':settings.bank_mode.value,'outcome':'SUCCESS' if response.status_code<400 else 'REJECTED',
                'customer_reference':getattr(request.state,'customer_reference',None),
            }
            metadata.update(getattr(request.state,'log_fields',{}))
            try:
                BankProtection(settings).record(metadata,
                    kept=getattr(request.state,'kept_paths',()),
                    removed=protection.removed_paths if protection else (),
                    warnings=protection.warnings if protection else (),latency_ms=(time.perf_counter()-started)*1000,
                    account_id=getattr(request.state,'account_id',None),
                    source_paths=getattr(request.state,'source_paths',()),
                    contract_excluded=getattr(request.state,'contract_excluded',()),
                    header_actions=header_decisions(request.headers,response.headers),
                    policy_valid=protection.policy_valid if protection else None,
                    would_remove=protection.would_remove_paths if protection else ())
                response.headers['X-Nexus-Log-Protection']='SANITIZED'
            except Exception:
                # Never retry persistence using raw data. A transfer may already
                # have committed, so clients must keep their idempotency key.
                response=JSONResponse(status_code=503,content={'detail':'Protected audit unavailable. Retry a transfer with its same idempotency key.'})
            response.headers['X-Request-ID']=correlation
        response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault('X-Request-ID',correlation)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if bank_request and settings.response_inspection_demo and getattr(request.state,'inspection_status',None)==response.status_code:
            try:
                snapshots.put(correlation,endpoint,request.method,response.status_code,
                              request.scope.get('http_version','1.1'),response.headers,request.state.inspection_payload)
            except Exception:
                pass  # Inspection must not alter a customer response or retry a payment.
        return response

    def load_policy():
        with PolicyStore(settings.database_path) as store:
            return store.get()

    def current_digest():
        return analysis_digest(golden_analysis())

    def sink():
        return LogSink(settings.database_path)

    def policy_state(store):
        history = store.history()
        return {
            "synthetic": True, "policy": store.get().to_dict() if history else None,
            "history": history, "current_analysis_digest": current_digest(),
        }

    def run_account(mode: RuntimeMode):
        original = golden_payload()
        result = APIEnforcer(load_policy).enforce(original, mode, expected_analysis_digest=current_digest())
        trace = result.to_dict()
        trace.pop("payload", None)
        try:
            sink().record_audit("API_RESPONSE", policy_revision=result.policy_revision, mode=mode.value, warnings=result.warnings)
        except Exception:
            # If trace persistence fails, return all original data rather than
            # making an unrecorded removal. Never expose the exception payload.
            return original, original, {
                "mode": mode.value, "policy_revision": None, "policy_valid": False,
                "warnings": ["Audit persistence unavailable; response minimisation bypassed safely."],
                "removed_paths": [], "would_remove_paths": [],
            }
        return original, result.payload, trace

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Invalid request parameters."})

    @app.get("/health")
    def health():
        return {"status": "ok", "synthetic": True}

    @app.get('/ready')
    def ready():
        from .bank.service import Bank
        bank=Bank(settings.database_path)
        with bank.connection(True) as db:
            db.execute('SELECT 1').fetchone()
        return {'status':'ready','synthetic':True,'database':'available'}

    @app.get("/api/analysis")
    def analysis():
        return golden_analysis()

    @app.get("/api/policy")
    def policy():
        with PolicyStore(settings.database_path) as store:
            return policy_state(store)

    @app.post("/api/policy/revisions")
    def create_revision(body: RevisionRequest):
        with PolicyStore(settings.database_path) as store:
            history = store.history()
            mapping = store.get().log_mapping if history else None
            store.create_revision(golden_analysis(), log_mapping=mapping, force_new=body.new_revision)
            return policy_state(store)

    @app.post("/api/policy/review")
    def review(body: ReviewRequest):
        try:
            with PolicyStore(settings.database_path) as store:
                current = store.get(body.revision_id)
                if (body.analysis_digest != current.revision.analysis_digest
                    or body.inputs_digest != current.revision.inputs_digest
                    or current.revision.analysis_digest != current_digest()):
                    raise ValueError("Stale review")
                store.review(body.revision_id, body.reviewer, body.approved_fields, notes=body.notes, decision=body.decision)
                return policy_state(store)
        except (PolicyStoreError, ValueError, TypeError):
            raise HTTPException(status_code=409, detail="Review rejected; reload the current revision and select eligible candidates only.") from None

    @app.get("/api/demo/account")
    def account(mode: RuntimeMode | None = Query(default=None)):
        original, output, trace = run_account(mode or settings.mode)
        return {"synthetic": True, "original": original, "output": output, "trace": trace}

    @app.get("/api/demo/account/response")
    def account_response():
        _original, output, _trace = run_account(settings.mode)
        return output

    @app.post("/api/demo/log")
    def protected_log():
        original = golden_log_event()
        log_sink = sink()
        result = StructuredLogPipeline(load_policy, log_sink, settings.hmac_key).process(
            original, expected_analysis_digest=current_digest(),
        )
        trace = result.to_dict()
        trace.pop("event", None)
        return {
            "synthetic": True, "original": original, "sanitized": result.event,
            "persisted": log_sink.get(result.record_id), "trace": trace,
        }

    @app.post("/api/verify")
    def verify(body: VerifyRequest):
        return verify_paths(
            load_policy, sink(), expected_analysis_digest=current_digest(),
            revision_id=body.revision_id, hmac_key=settings.hmac_key,
        )

    @app.get('/api/traffic')
    def traffic():
        return {'events':BankProtection(settings).events(),'retention':1000,'poll_interval_seconds':3}

    def bank_policy_state(store):
        history=store.history()
        return {'synthetic':True,'policy':store.get().to_dict() if history else None,'history':history,
                'destination':'nexus_bank.account_summary.v1','current_analysis_digest':analysis_digest(account_report())}

    @app.get('/api/bank-policy')
    def bank_policy():
        with PolicyStore(BankProtection(settings).policy_path) as store:
            return bank_policy_state(store)

    @app.post('/api/bank-policy/revisions')
    def bank_revision(body:RevisionRequest):
        with PolicyStore(BankProtection(settings).policy_path) as store:
            store.create_revision(account_report(),force_new=body.new_revision)
            return bank_policy_state(store)

    @app.post('/api/bank-policy/review')
    def bank_review(body:ReviewRequest):
        try:
            with PolicyStore(BankProtection(settings).policy_path) as store:
                p=store.get(body.revision_id)
                if (p.revision.analysis_digest!=body.analysis_digest or p.revision.inputs_digest!=body.inputs_digest
                    or p.revision.analysis_digest!=analysis_digest(account_report())):
                    raise ValueError('Stale review')
                store.review(body.revision_id,body.reviewer,body.approved_fields,notes=body.notes,decision=body.decision)
                return bank_policy_state(store)
        except ValueError:
            raise HTTPException(status_code=409,detail='Review rejected; reload the endpoint-specific revision.') from None

    @app.get('/api/bank-analysis')
    def bank_analysis():
        report=account_report()
        return {**report,'counts':{usage:sum(f['usage']==usage for f in report['fields']) for usage in ('USED','CANDIDATE_UNUSED','UNKNOWN')}}

    @app.get('/api/operator/accounts')
    def operator_accounts(search:str=Query(default='',max_length=120),limit:int=Query(default=25,ge=1,le=100),
                          offset:int=Query(default=0,ge=0,le=100000),reveal:bool=False):
        from .bank.explorer import AccountExplorer
        return AccountExplorer(settings).accounts(search,limit,offset,reveal)

    @app.get('/api/operator/accounts/{account_id}')
    def operator_account(account_id:str,reveal:bool=False):
        from .bank.explorer import AccountExplorer
        return AccountExplorer(settings).account(account_id,reveal)

    @app.get('/api/operator/events/{event_id}')
    def operator_event(event_id:int):
        from .bank.explorer import AccountExplorer
        return AccountExplorer(settings).event(event_id)

    return app
