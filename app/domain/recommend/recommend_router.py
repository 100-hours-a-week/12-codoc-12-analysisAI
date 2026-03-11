import logging
import time

from fastapi import APIRouter

from app.common.api_response import CommonResponse
from app.common.exceptions.custom_exception import (
    InvalidStarterConditionException,
    RecommendationNotFoundException,
)
from app.common.observability.metrics import (
    RECOMMEND_DURATION_SECONDS,
    RECOMMEND_REQUEST_TOTAL,
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
logger = logging.getLogger("codoc.recommend")

def _merge_to_five(base_ids: list[str], static_ids: list[str], desired_count:int=5,)-> list[str]:
    merged = []
    seen = set()

    for pid in base_ids + static_ids:
        if pid in seen:
            continue
        seen.add(pid)
        merged.append(pid)
        if len(merged) >= desired_count:
            break

    return merged

@router.post("", response_model=CommonResponse[RecommendResponseData])
async def get_recommendations(request: RecommendRequest):
    started_at = time.perf_counter()
    success = False
    try:
        solved_ids = request.filter_info.solved_problem_ids
        challenge_ids = request.filter_info.challenge_problem_ids

        recommendation_items: list[dict] = []

        if request.scenario == "NEW":
            if len(solved_ids) >= 5:
                raise InvalidStarterConditionException()

            static_result = await recommend_service.get_static_recomendations(
                user_level=request.user_level,
                solved_problem_ids=solved_ids,
                challenge_problem_ids=challenge_ids,
                limit=5,
            )

            if "recommended_problem_ids" not in static_result:
                raise RecommendationNotFoundException(
                    static_result.get("message", "추천 결과가 없습니다.")
                )


            for pid in static_result["recommended_problem_ids"]:
                recommendation_items.append(
                    {
                        "problem_id": int(pid),
                        "weak_tags": static_result.get("weak_tags",[]),
                        "reason_context": static_result.get("reason_context", {}),
                    }
                )
        else:
            current_prob = challenge_ids[-1] if challenge_ids else 0
            collab_result = await recommend_service.get_collaborative_recommendations(
                user_id=request.user_id,
                current_problem_id=current_prob,
                exclude_ids=solved_ids,
                limit=5,
            )

            collab_ids = collab_result.get("recommended_problem_ids",[])
            collab_context = collab_result.get("reason_context", {})
            collab_weak_tags = collab_result.get("weak_tags", [])

            if len(collab_ids) < 5:
                extra_excluded = [int(x) for x in collab_ids]
                static_fill_result = await recommend_service.get_static_recomendations(
                    user_level=request.user_level,
                    solved_problem_ids=solved_ids + extra_excluded,
                    challenge_problem_ids=challenge_ids + extra_excluded,
                    limit=10,
                )
                static_fill_ids = static_fill_result.get("recommended_problem_ids", [])
            else:
                static_fill_result = {}
                static_fill_ids = []

            merged_ids = _merge_to_five(collab_ids, static_fill_ids, desired_count=5)

            if not merged_ids:
                raise RecommendationNotFoundException(
                    collab_result.get("message", "추천 결과가 없습니다.")
                )

            collab_id_set = set(collab_ids)
            for pid in merged_ids:
                if pid in collab_id_set:
                    recommendation_items.append(
                        {
                            "problem_id": int(pid),
                            "weak_tags": collab_weak_tags,
                            "reason_context": collab_context,
                        }
                    )
                else:
                    recommendation_items.append(
                        {
                            "problem_id": int(pid),
                            "weak_tags": static_fill_result.get("weak_tags", []),
                            "reason_context": static_fill_result.get("reason_context", {}),
                        }
                    )

        recommendations =  []

        for item in recommendation_items:
            problem_id = item["problem_id"]
            problem_payload = await vector_db.get_problem_by_id(problem_id)

            print(f"[DEBUG] problem_id={problem_id}")
            print(f"[DEBUG] problem_payload={problem_payload}")

            reason_msg = await recommend_llm_service.generate_reason(
                scenario=request.scenario,
                user_level=request.user_level,
                weak_tags=item["weak_tags"],
                problem_payload=problem_payload,
                recommendation_context=item["reason_context"],
            )

            recommendations.append(
                ProblemRecommendation(
                    problem_id=problem_id,
                    reason_msg=reason_msg,
                )
            )

        if not recommendations:
            raise RecommendationNotFoundException("추천 결과가 없습니다.")

        response_data = RecommendResponseData(
            user_id=request.user_id,
            scenario=request.scenario,
            recommendations=recommendations,
        )
        success = True
        return CommonResponse.success_response(message="OK", data=response_data)
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
