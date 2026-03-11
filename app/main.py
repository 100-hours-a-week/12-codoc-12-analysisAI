import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.common.exceptions.exception_handler import register_exception_handlers
from app.common.observability import setup_logging
from app.common.observability.metrics import (
    HTTP_ERRORS_TOTAL,
    HTTP_IN_PROGRESS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from app.core.config import settings
from app.database.vector_db import vector_db
from app.domain.recommend import recommend_router
from app.domain.report import report_router

setup_logging()
logger = logging.getLogger("codoc.api")

app = FastAPI(title="Codoc AI Server", version="2.0.0")
register_exception_handlers(app)

app.include_router(
    recommend_router.router,
    prefix=f"{settings.API_PREFIX}/recommend",
    tags=["Recommendation"],
)
app.include_router(
    report_router.router,
    prefix=f"{settings.API_PREFIX}/reports",
    tags=["Report"],
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    method = request.method
    status_code = 500
    path = request.url.path
    request_id = request.headers.get("x-request-id", uuid4().hex)
    user_agent = request.headers.get("user-agent", "")

    HTTP_IN_PROGRESS.labels(method=method).inc()
    try:
        response = await call_next(request)
        status_code = response.status_code
        route = request.scope.get("route")
        if route is not None and hasattr(route, "path"):
            path = route.path
        return response
    finally:
        duration = time.perf_counter() - started_at
        status = str(status_code)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        if status_code >= 500:
            HTTP_ERRORS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        HTTP_IN_PROGRESS.labels(method=method).dec()
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(duration * 1000, 2),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": user_agent,
                },
                ensure_ascii=False,
            )
        )


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Codoc AI Server is running"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/db")
async def check_db_connection():
    try:
        collections = vector_db.client.get_collections()
        return {
            "status": "connected",
            "details": "Successfully reached Qdrant DB",
            "collections": collections,
        }
    except Exception as e:
        return {"status": "error", "details": f"Failed to connect to Qdrant: {str(e)}"}
