import logging
import os
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.common.exceptions.exception_handler import register_exception_handlers
from app.common.observability import setup_logging, setup_otlp
from app.common.observability.metrics import (
    FASTAPI_APP_INFO,
    FASTAPI_REQUEST_DURATION_SECONDS,
    FASTAPI_REQUESTS_IN_PROGRESS,
    FASTAPI_REQUESTS_TOTAL,
    FASTAPI_RESPONSES_TOTAL,
    HTTP_ERRORS_TOTAL,
    HTTP_IN_PROGRESS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    resolve_request_path,
)
from app.core.config import settings
from app.database.vector_db import vector_db
from app.domain.recommend import recommend_router
from app.domain.report import report_router

setup_logging()
logger = logging.getLogger("codoc.api")
APP_NAME = os.getenv("APP_NAME", "app-analysis")
OTLP_GRPC_ENDPOINT = os.getenv("OTLP_GRPC_ENDPOINT", "").strip()

app = FastAPI(title="Codoc AI Server", version="2.0.0")
register_exception_handlers(app)
FASTAPI_APP_INFO.labels(app_name=APP_NAME).set(1)
if OTLP_GRPC_ENDPOINT:
    setup_otlp(app, APP_NAME, OTLP_GRPC_ENDPOINT, log_correlation=True)

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
# app.include_router(
#     router=workbook_router.router,
#     prefix=f"{settings.API_PREFIX}/ocr",
#     tags=["Workbook"],
# )

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    method = request.method
    status_code = 500
    path, is_handled_path = resolve_request_path(request)
    request_id = request.headers.get("x-request-id", uuid4().hex)
    user_agent = request.headers.get("user-agent", "")

    HTTP_IN_PROGRESS.labels(method=method).inc()
    fastapi_labels = {"method": method, "path": path, "app_name": APP_NAME}
    if is_handled_path:
        FASTAPI_REQUESTS_IN_PROGRESS.labels(**fastapi_labels).inc()
        FASTAPI_REQUESTS_TOTAL.labels(**fastapi_labels).inc()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - started_at
        status = str(status_code)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        if status_code >= 500:
            HTTP_ERRORS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        HTTP_IN_PROGRESS.labels(method=method).dec()
        if is_handled_path:
            FASTAPI_RESPONSES_TOTAL.labels(
                method=method,
                path=path,
                status_code=status,
                app_name=APP_NAME,
            ).inc()
            FASTAPI_REQUEST_DURATION_SECONDS.labels(**fastapi_labels).observe(duration)
            FASTAPI_REQUESTS_IN_PROGRESS.labels(**fastapi_labels).dec()
        logger.info(
            "event=http_request request_id=%s method=%s path=%s status_code=%s latency_ms=%.2f client_ip=%s user_agent=%s",
            request_id,
            method,
            path,
            status_code,
            duration * 1000,
            request.client.host if request.client else "-",
            user_agent or "-",
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
