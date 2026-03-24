from typing import Any
from app.common.exceptions.custom_exception import (
    InvalidStarterConditionException,
    RecommendationNotFoundException
)
from app.database.vector_db import vector_db
from app.domain.recommend.recommend_llm_service import recommend_llm_service
from app.domain.recommend.recommend_service import recommend_service
from app.domain.recommend.recommendation_schemas import ProblemRecommendation, RecommendRequest, RecommendResponseData
from app.domain.recommend.recommend_rag_service import recommend_rag_service

def _merge_to_five(
        base_ids: list[str], static_ids: list[str], desired_count: int=5
) -> list[str]:
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

# tags 리스트 구조 고정
def _normalize_tags(value:Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, str):
        text = value.replace("|", ",").replace("/",",")
        return [p.strip() for p in text.split(",") if p.strip()]

    return []

def _normalize_difficulty(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0
        try:
            return max(0, int(float(s)))
        except ValueError:
            return 0
    return 0

# payload 정보 품질 검증
def _normalize_problem_payload(
        expected_problem_id: int,
        payload: dict[str, Any] | None,
)-> tuple[dict[str, Any] | None, list[str], list[str], list[str]]:

    # required_missing : 필수 항목 중 누락 필드
    # recommended_missing : 권장 항목 중 누락 필드
    required_missing: list[str] = []
    recommended_missing: list[str] = []
    normalized_notes: list[str] = []

    if not isinstance(payload, dict):
        return None, ["problem_payload"], ["title", "tags", "summary"], normalized_notes

    normalized = dict(payload)

    pid = normalized.get("problem_id")
    if pid is None:
        required_missing.append("problem_id")
    else:
        try:
            if int(pid) != int(expected_problem_id):
                required_missing.append("problem_id_mismatch")
        except (TypeError, ValueError):
            required_missing.append("problem_id_invalid_type")

    title = normalized.get("title")
    normalized["title"] = title.strip() if isinstance(title, str) else ""
    if not normalized["title"]:
        recommended_missing.append("title")

    tags = _normalize_tags(normalized.get("tags"))
    if tags:
        normalized["tags"] = tags
    else:
        alt_tags = _normalize_tags(normalized.get("problem_algorithm_tag"))
        if alt_tags:
            normalized["tags"] = alt_tags
            normalized_notes.append("tags<-problem_algorithm_tag")
            recommended_missing.append("tags")
        else:
            normalized["tags"] = []
            normalized_notes.append("tags<-default([])")
            recommended_missing.append("tags")

    # 난이도 숫자/문자열 혼용 정리
    raw_difficulty = normalized.get("difficulty", normalized.get("level"))
    normalized["difficulty"] = _normalize_difficulty(raw_difficulty)

    summary = normalized.get("summary")
    if isinstance(summary, str) and summary.strip():
        normalized["summary"] = summary.strip()
    else:
        alt_summary = normalized.get("essential_summary")
        if isinstance(alt_summary, str) and alt_summary.strip():
            normalized["summary"] = alt_summary.strip()
            normalized_notes.append("summary<-essential_summary")
            recommended_missing.append("summary")
        else:
            normalized["summary"] = "핵심 조건과 출력 형식을 점검해볼 수 있는 문제입니다."
            normalized_notes.append("summary<-default")
            recommended_missing.append("summary")

    if required_missing:
        return None, required_missing, recommended_missing, normalized_notes

    return normalized, required_missing, recommended_missing, normalized_notes


async def generate_recommendations_usecase(request: RecommendRequest) -> RecommendResponseData:
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
                    "weak_tags": static_result.get("weak_tags", []),
                    "reason_context": static_result.get("reason_context", {})
                }
            )
    else:
        current_prob = challenge_ids[-1] if challenge_ids else 0
        collab_result = await recommend_service.get_collaborative_recommendations(
            user_id = request.user_id,
            current_problem_id=current_prob,
            exclude_ids=solved_ids,
            limit=5,
        )

        collab_ids = collab_result.get("recommended_problem_ids", [])
        collab_context = collab_result.get("reason_context", {})
        collab_weak_tags = collab_result.get("weak_tags", [])

        if len(collab_ids) < 5:
            extra_excluded = [int(x) for x in collab_ids]
            static_fill_result = await recommend_service.get_static_recomendations(
                user_level=request.user_level,
                solved_problem_ids=solved_ids+extra_excluded,
                challenge_problem_ids=challenge_ids+extra_excluded,
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

    recommendations = []
    batch_items: list[dict[str, Any]] = []

    for idx, item in enumerate(recommendation_items):
        problem_id = item["problem_id"]

        evidence_docs = await recommend_rag_service.retrieve_problem_evidence(
            problem_id=problem_id,
            scenario=request.scenario,
            weak_tags=item["weak_tags"],
            recommendation_context=item["reason_context"],
            top_k=2,
        )
        raw_payload = await vector_db.get_problem_by_id(problem_id)
        problem_payload, required_missing, recommended_missing, normalized_notes = _normalize_problem_payload(
            expected_problem_id=problem_id,
            payload=raw_payload,
        )

        if required_missing:
            print(
                f"[QUALITY][REQUIRED_MISSING] problem_id={problem_id}, missing={required_missing}"
            )
            problem_payload = None
        elif recommended_missing:
            print(
                f"[QUALITY][RECOMMENDED_MISSING] problem_id={problem_id}, missing={recommended_missing}"
            )
        if normalized_notes:
            print(
                f"[QUALITY][NORMALIZED] problem_id={problem_id}, notes={normalized_notes}"
            )


        batch_items.append(
            {
                "problem_id": problem_id,
                "weak_tags": item["weak_tags"],
                "recommendation_context": item["reason_context"],
                "problem_payload": problem_payload,
                "evidence_docs": evidence_docs,
                "fallback_slot": idx,
            }
        )

    reason_map = await recommend_llm_service.generate_reasons_batch(
        scenario=request.scenario,
        user_level=request.user_level,
        items=batch_items,
    )


    for item in batch_items:
        pid = item["problem_id"]
        recommendations.append(
            ProblemRecommendation(
                problem_id=pid,
                reason_msg=reason_map.get(pid, "핵심 포인트를 점검해볼 수 있어요!"),
            )
        )

    if not recommendations:
        raise RecommendationNotFoundException("추천 결과가 없습니다.")

    return RecommendResponseData(
        user_id=request.user_id,
        scenario=request.scenario,
        recommendations=recommendations,
    )
