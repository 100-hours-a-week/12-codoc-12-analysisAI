from typing import Any
from qdrant_client.http import models

from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service

class RecommendRagService:
    def __init__(self):
        self.vector_db = vector_db
        self.collection_name = vector_db.problem_collection
        self.default_top_k = 2

    async def retrieve_problem_evidence(
            self,
            *,
            problem_id: int,
            scenario: str,
            weak_tags: list[str],
            recommendation_context: dict[str, Any],
            top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        query_text = self._build_query_text(
            scenario=scenario,
            weak_tags=weak_tags,
            recommendation_context=recommendation_context,
        )
        limit = top_k or self.default_top_k
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="problem_id",
                    match=models.MatchValue(value=problem_id),
                )
            ]
        )

        points: list[Any] = []
        try:
            query_vector = embedding_service.get_embedding(query_text)
            result = self.vector_db.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            points = getattr(result, "points", []) or []
        except Exception as e:
            print(f"[DEBUG] recommend RAG query failed problem_id={problem_id}: {e}")

        if not points:
            try:
                rows, _ = self.vector_db.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter={
                        "must": [{"key": "problem_id", "match": {"value": problem_id}}]
                    },
                    limit=limit,
                    with_payload=True,
                )
                points = sorted(
                    rows,
                    key=lambda row: int((row.payload or {}).get("paragraph_order", 9999)),
                )
            except Exception as e:
                print(f"[DEBUG] recommend RAG fallback scroll failed problem_id={problem_id}: {e}")
                return []

        evidence_docs: list[dict[str,Any]] = []
        seen_sections: set[str] = set()
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            section = str(payload.get("paragraph_type", "UNKNOWN"))
            if section in seen_sections:
                continue
            seen_sections.add(section)

            evidence_docs.append(
                {
                    "rank": rank,
                    "score": round(float(point.score), 4)
                    if getattr(point, "score", None) is not None
                    else None,
                    "paragraph_type": section,
                    "essential_summary": payload.get("essential_summary", ""),
                    "essential_keywords": payload.get("essential_keywords", []),
                    "chatbot_answer_guide": payload.get("chatbot_answer_guide", ""),
                    "content": payload.get("content", ""),
                }
            )
        return evidence_docs

    def _build_query_text(
        self,
        *,
        scenario: str,
        weak_tags: list[str],
        recommendation_context: dict[str, Any],
    ) -> str:
        matched_tags = recommendation_context.get("matched_tags", [])
        focus_tags = weak_tags or matched_tags
        recommendation_type = recommendation_context.get("recommendation_type", "")
        basis = (
            recommendation_context.get("collaborative_basis", "")
            or recommendation_context.get("starter_basis", "")
            or ""
        )

        return (
            f"scenario={scenario}\n"
            f"recommendation_type={recommendation_type}\n"
            f"focus_tags={','.join(str(tag) for tag in focus_tags)}\n"
            f"basis={basis}\n"
            "goal=추천 사유 근거 검색"
        )

recommend_rag_service = RecommendRagService()