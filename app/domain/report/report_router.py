import logging
import time

from fastapi import APIRouter

from app.common.api_response import CommonResponse
from app.common.observability.metrics import (
    REPORT_BATCH_DURATION_SECONDS,
    REPORT_BATCH_TOTAL,
)
from app.domain.report.report_schemas import ReportRequest, ReportResponseData
from app.domain.report.report_service import report_service

router = APIRouter()
logger = logging.getLogger("codoc.report")

@router.post("", response_model=CommonResponse[ReportResponseData])
async def generate_report(request: ReportRequest):
    started_at = time.perf_counter()
    success = False
    try:
        data = await report_service.generate_report(request)
        success = True
        return CommonResponse.success_response(message="OK", data=data)
    finally:
        duration = time.perf_counter() - started_at
        REPORT_BATCH_DURATION_SECONDS.observe(duration)
        REPORT_BATCH_TOTAL.labels(status="success" if success else "fail").inc()
        logger.info(
            "event=report_batch user_id=%s status=%s latency_ms=%.2f",
            request.user_id,
            "success" if success else "fail",
            duration * 1000,
        )
