import logging
import os


class OpenTelemetryContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.otelTraceID = getattr(record, "otelTraceID", "0")
        record.otelSpanID = getattr(record, "otelSpanID", "0")
        record.otelServiceName = getattr(
            record,
            "otelServiceName",
            os.getenv("APP_NAME", "app-analysis"),
        )
        return True


def setup_logging() -> None:
    """Configure a text logger that matches the shared FastAPI observability dashboard."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.addFilter(OpenTelemetryContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
            "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
