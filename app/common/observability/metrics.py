from prometheus_client import Counter, Gauge, Histogram

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
