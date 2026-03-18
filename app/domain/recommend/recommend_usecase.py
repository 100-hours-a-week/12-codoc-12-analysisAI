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


def _merge_to_five(
    base_ids: list[str], static_ids: list[str], desired_count: int = 5
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for pid in base_ids + static_ids:
        if pid in seen:
            continue
        seen.add(pid)
        merged.append(pid)
        if len(merged) >= desired_count:
            break

    return merged


def _reason_from_context(reason_context: dict, default_msg: str) -> str:
    if not isinstance(reason_context, dict):
        return default_msg

    recommendation_type = reason_context.get("recommendation_type")
    if recommendation_type == "collaborative":
        return reason_context.get(
            "collaborative_basis", "유사한 풀이 패턴을 기반으로 추천한 문제입니다."
        )

    if recommendation_type == "static":
        return reason_context.get(
            "starter_basis", "초기 사용자 학습 흐름을 위한 추천 문제입니다."
        )

    return default_msg


async def generate_recommendations_usecase(
    request: RecommendRequest,
) -> RecommendResponseData:
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

        static_reason = _reason_from_context(
            static_result.get("reason_context", {}),
            "초기 사용자 학습 흐름을 위한 추천 문제입니다.",
        )

        for pid in static_result["recommended_problem_ids"]:
            recommendation_items.append(
                {
                    "problem_id": int(pid),
                    "reason_msg": static_reason,
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

        collab_ids = collab_result.get("recommended_problem_ids", [])
        collab_context = collab_result.get("reason_context", {})

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

        collab_reason = _reason_from_context(
            collab_context,
            "유사한 풀이 패턴을 기반으로 추천한 문제입니다.",
        )
        static_reason = _reason_from_context(
            static_fill_result.get("reason_context", {}),
            "초기 사용자 학습 흐름을 위한 추천 문제입니다.",
        )

        collab_id_set = set(collab_ids)
        for pid in merged_ids:
            recommendation_items.append(
                {
                    "problem_id": int(pid),
                    "reason_msg": collab_reason if pid in collab_id_set else static_reason,
                }
            )

    recommendations = [
        ProblemRecommendation(
            problem_id=item["problem_id"],
            reason_msg=item["reason_msg"],
        )
        for item in recommendation_items
    ]

    if not recommendations:
        raise RecommendationNotFoundException("추천 결과가 없습니다.")

    return RecommendResponseData(
        user_id=request.user_id,
        scenario=request.scenario,
        recommendations=recommendations,
    )
