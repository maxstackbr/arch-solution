import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.routes_balance import router as balance_router
from app.config import settings
from app.infra.cache import cache_health
from app.infra.db import Base, SessionLocal, engine
from app.observability.logging import configure_logging, correlation_id
from app.observability.metrics import (
    consolidation_requests_rejected_total,
    http_request_duration_seconds,
    http_requests_total,
)
from app.resilience.load_shedding import ConcurrencyLimiter

configure_logging("consolidation")

limiter = ConcurrencyLimiter(settings.max_concurrency)
# Infrastructure traffic: never load-shed, and kept out of the metrics that the RNF-2
# rejection ratio is computed from (docs/04-observability.md).
_EXEMPT_PATHS = {"/health", "/metrics"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Simplified schema management for the challenge — a real deployment would use
    # Alembic migrations instead of create_all (see docs/08-future-work.md).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Consolidation Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def load_shedding_middleware(request: Request, call_next):
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)

    acquired = await limiter.try_acquire()
    if not acquired:
        consolidation_requests_rejected_total.inc()
        return JSONResponse(
            status_code=503,
            content={"detail": "Service overloaded, please retry"},
            headers={"Retry-After": "1"},
        )
    try:
        return await call_next(request)
    finally:
        await limiter.release()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    route = request.scope.get("route")
    # A load-shed 503 never reaches the router, so there is no matched route to label it with.
    # Falling back to the raw path would give every requested date its own Prometheus series.
    route_path = route.path if route else "<unmatched>"
    http_requests_total.labels(route=route_path, method=request.method, status=response.status_code).inc()
    http_request_duration_seconds.labels(route=route_path).observe(duration)
    return response


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    correlation_id.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(balance_router)


@app.get("/health")
def health():
    db_status = "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    # A cache outage degrades performance (reads fall back to Postgres) but does not make the
    # service unhealthy — only the database is a hard dependency here.
    cache_status = "ok" if cache_health() else "degraded"
    status_code = 503 if db_status != "ok" else 200
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "error",
            "database": db_status,
            "cache": cache_status,
        },
    )


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
