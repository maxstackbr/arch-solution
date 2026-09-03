import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.routes_entries import router as entries_router
from app.config import settings
from app.infra.db import Base, SessionLocal, engine
from app.observability.logging import configure_logging, correlation_id
from app.observability.metrics import http_request_duration_seconds, http_requests_total

configure_logging("ledger")

# Infrastructure traffic: excluded so it does not dilute the request/error rates the
# RNF dashboards are computed from (docs/04-observability.md).
_UNMETERED_PATHS = {"/health", "/metrics"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Simplified schema management for the challenge — a real deployment would use
    # Alembic migrations instead of create_all (see docs/08-future-work.md).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Ledger Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    correlation_id.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path in _UNMETERED_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    route = request.scope.get("route")
    # Falling back to the raw path would make every unmatched URL (404s, scanners) its own
    # Prometheus series; unrouted traffic is collapsed into one label instead.
    route_path = route.path if route else "<unmatched>"
    http_requests_total.labels(route=route_path, method=request.method, status=response.status_code).inc()
    http_request_duration_seconds.labels(route=route_path).observe(duration)
    return response


app.include_router(entries_router)


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception:
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
