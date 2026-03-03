from fastapi import APIRouter, HTTPException

from app.common.api_response import CommonResponse
from app.common.exceptions.custom_exception import (
    InvalidStarterConditionException,
    RecommendationNotFoundException,
)
from app.database.vector_db import vector_db
from app.domain.recommend.recommend_llm_service import recommend_llm_service
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

    weak_tags = recommend_result.get("weak_tags", [])
    reason_context = recommend_result.get("reason_context", {})
    recommendations = []


    for p_id in recommend_result["recommended_problem_ids"]:
        problem_id = int(p_id)
        problem_payload = await vector_db.get_problem_by_id(problem_id)

        print(f"[DEBUG] problem_id={problem_id}")
        print(f"[DEBUG] problem_payload={problem_payload}")

        reason_msg = await recommend_llm_service.generate_reason(
            scenario=request.scenario,
            user_level=request.user_level,
            weak_tags=weak_tags,
            problem_payload=problem_payload,
            recommendation_context=reason_context,
        )

        recommendations.append(
            ProblemRecommendation(
                problem_id=problem_id,
                reason_msg=reason_msg,
            )
        )

    response_data = RecommendResponseData(
        user_id=request.user_id,
        scenario=request.scenario,
        recommendations=recommendations,
    )
    return CommonResponse.success_response(message="OK", data=response_data)