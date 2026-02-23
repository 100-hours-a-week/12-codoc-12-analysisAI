from fastapi import APIRouter, HTTPException

from app.common.api_response import CommonResponse
from app.common.exceptions.custom_exception import (
    InvalidStarterConditionException,
    RecommendationNotFoundException,
)
from app.domain.recommend.recommend_service import recommend_service
from app.domain.recommend.recommendation_schemas import (
    ProblemRecommendation,
    RecommendRequest,
    RecommendResponseData,
)

router = APIRouter()


@router.post("", response_model=CommonResponse[RecommendResponseData])
async def get_recommendations(request: RecommendRequest):
    solved_ids = request.filter_info.solved_problem_ids
    challenge_ids = request.filter_info.challenge_problem_ids


    if request.scenario == "NEW":
        if len(solved_ids) >= 5:
            raise InvalidStarterConditionException()

        recommend_result = await recommend_service.get_static_recomendations(
            user_level=request.user_level,
            solved_problem_ids=solved_ids,
            challenge_problem_ids=challenge_ids,
        )
    else:
        current_prob = challenge_ids[-1] if challenge_ids else 0
        recommend_result = await recommend_service.get_collaborative_recommendations(
                user_id=request.user_id,
                current_problem_id=current_prob,
                exclude_ids=solved_ids,
        )



    if "recommended_problem_ids" not in recommend_result:
        raise RecommendationNotFoundException(
            recommend_result.get("message", "추천 결과가 없습니다.")
        )

    recommendations = [
        ProblemRecommendation(
            problem_id=int(p_id),
            reason_msg=recommend_result["reason"],
        )
        for p_id in recommend_result["recommended_problem_ids"]
    ]

    response_data = RecommendResponseData(
        user_id=request.user_id,
        scenario=request.scenario,
        recommendations=recommendations,
    )
    return CommonResponse.success_response(message="OK", data=response_data)