from typing import Tuple

from prometheus_client import Counter, Gauge, Histogram
from starlette.requests import Request
from starlette.routing import Match

HTTP_REQUESTS_TOTAL = Counter(
    "codoc_http_requests_total",
    "Total number of HTTP requests.",
    ["method", "path", "status"],
)

HTTP_ERRORS_TOTAL = Counter(
    "codoc_http_errors_total",
    "Total number of HTTP requests that resulted in server errors.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "codoc_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)

HTTP_IN_PROGRESS = Gauge(
    "codoc_http_in_progress",
    "Number of in-progress HTTP requests.",
    ["method"],
)

FASTAPI_APP_INFO = Gauge(
    "fastapi_app_info",
    "FastAPI application information.",
    ["app_name"],
)

FASTAPI_REQUESTS_TOTAL = Counter(
    "fastapi_requests_total",
    "Total count of requests by method and path.",
    ["method", "path", "app_name"],
)

FASTAPI_RESPONSES_TOTAL = Counter(
    "fastapi_responses_total",
    "Total count of responses by method, path and status codes.",
    ["method", "path", "status_code", "app_name"],
)

FASTAPI_REQUEST_DURATION_SECONDS = Histogram(
    "fastapi_requests_duration_seconds",
    "Histogram of requests processing time by path (in seconds).",
    ["method", "path", "app_name"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)

FASTAPI_EXCEPTIONS_TOTAL = Counter(
    "fastapi_exceptions_total",
    "Total count of exceptions raised by path and exception type.",
    ["method", "path", "exception_type", "app_name"],
)

FASTAPI_REQUESTS_IN_PROGRESS = Gauge(
    "fastapi_requests_in_progress",
    "Gauge of requests by method and path currently being processed.",
    ["method", "path", "app_name"],
)

REPORT_BATCH_TOTAL = Counter(
    "codoc_report_batch_total",
    "Total number of report batch jobs by status.",
    ["status"],
)

REPORT_BATCH_DURATION_SECONDS = Histogram(
    "codoc_report_batch_duration_seconds",
    "Total time taken to generate one report batch.",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60),
)

RECOMMEND_REQUEST_TOTAL = Counter(
    "codoc_recommend_request_total",
    "Total number of recommendation requests by status.",
    ["status"],
)

RECOMMEND_DURATION_SECONDS = Histogram(
    "codoc_recommend_duration_seconds",
    "Time taken to generate recommendations.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10),
)

LLM_TOKENS_TOTAL = Counter(
    "codoc_llm_tokens_total",
    "Total token usage from LLM calls.",
    ["service", "token_type"],
)

LLM_COST_TOTAL_USD = Counter(
    "codoc_llm_cost_total_usd",
    "Accumulated LLM usage cost in USD.",
    ["service"],
)

LLM_COST_PER_REQUEST_USD = Histogram(
    "codoc_llm_cost_per_request_usd",
    "Per-request LLM cost in USD.",
    ["service"],
    buckets=(0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05),
)


def resolve_request_path(request: Request) -> Tuple[str, bool]:
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path, True
    return request.url.path, False


def record_fastapi_exception(request: Request, exc: BaseException, app_name: str) -> None:
    path, is_handled_path = resolve_request_path(request)
    if not is_handled_path:
        return

    FASTAPI_EXCEPTIONS_TOTAL.labels(
        method=request.method,
        path=path,
        exception_type=type(exc).__name__,
        app_name=app_name,
    ).inc()
