from fastapi import APIRouter

from app.common.api_response import CommonResponse
from app.domain.recommend.recommend_usecase import generate_recommendations_usecase
from app.domain.recommend.recommendation_schemas import (
    RecommendRequest,
    RecommendResponseData,
)

router = APIRouter()


@router.post("", response_model=CommonResponse[RecommendResponseData])
async def get_recommendations(request: RecommendRequest):
    data = await generate_recommendations_usecase(request)
    return CommonResponse.success_response(message="OK", data=data)