import logging
import time

from fastapi import APIRouter

from app.common.api_response import CommonResponse
from app.domain.recommend.recommend_usecase import generate_recommendations_usecase
from app.common.observability.metrics import RECOMMEND_DURATION_SECONDS, RECOMMEND_REQUEST_TOTAL
from app.domain.recommend.recommendation_schemas import (
    RecommendRequest,
    RecommendResponseData,
)

router = APIRouter()
logger = logging.getLogger("codoc.recommend")


@router.post("", response_model=CommonResponse[RecommendResponseData])
async def get_recommendations(request: RecommendRequest):
    started_at = time.perf_counter()
    success = False
    try:
        data = await generate_recommendations_usecase(request)
        success = True
        return CommonResponse.success_response(message="OK", data=data)
    finally:
        duration = time.perf_counter() - started_at
        RECOMMEND_DURATION_SECONDS.observe(duration)
        RECOMMEND_REQUEST_TOTAL.labels(status="success" if success else "fail").inc()
        logger.info(
            "event=recommend_batch user_id=%s status=%s latency_ms=%.2f",
            request.user_id,
            "success" if success else "fail",
            duration * 1000,
        )
