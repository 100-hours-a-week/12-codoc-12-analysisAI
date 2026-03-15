from typing import Any
from qdrant_client.http import models

from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service

class ReportRagService:
    def __init__(self):
        self.vector_db = vector_db
        self.collection_name = "Algo_Concepts"
        self.default_top_k = 3

    async def retrieve_evidence(self, weak_section: str, weak_quiz: str, weakest_metric:str, user_level:str, top_k: int | None=None) -> list[dict[str,Any]]:
        query_text = self._build_query_text(
            weak_section=weak_section,
            weak_quiz=weak_quiz,
            weakest_metric=weakest_metric,
            user_level=user_level,
        )
        query_vector = embedding_service.get_embedding(query_text)

        query_filter = self._build_filter(weak_quiz)

        try:
            result = self.vector_db.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k or self.default_top_k,
                with_payload=True,
            )
        except Exception as e:
            print(f"[DEBUG] report RAG retrieval failed: {e}")
            return []

        points = getattr(result, "points", []) or []

        evidence_docs: list[dict[str, Any]] = []
        seen_concepts: set[str] = set()

        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            concept = payload.get("concept", "UNKNOWN")

            if concept in seen_concepts:
                continue
            seen_concepts.add(concept)

            evidence_docs.append({
                "rank": rank,
                "score": round(point.score, 4) if getattr(point, "score", None) is not None else None,
                "concept": concept,
                "name_ko": payload.get("name_ko", ""),
                "category": payload.get("category", ""),
                "definition": payload.get("definition", ""),
                "core_logic": payload.get("core_logic", ""),
                "complexity_guide": payload.get("complexity_guide", ""),
                "common_mistakes": payload.get("common_mistakes", []),
                "check_points": payload.get("check_points", []),
            })

        return evidence_docs

    def _build_query_text(self, weak_section: str, weak_quiz: str, weakest_metric: str, user_level:str) -> str:
        # TODO : 이거 3개 뭐임?
        section_hint = self._section_hint(weak_section)
        quiz_hint = self._quiz_hint(weak_quiz)
        metric_hint = self._metric_hint(weakest_metric)

        return(
            f"user_level={user_level}\n"
            f"weak_section={weak_section}\n"
            f"weak_quiz={weak_quiz}\n"
            f"weakest_metric={weakest_metric}\n"
            f"section_hint={section_hint}\n"
            f"quiz_hint={quiz_hint}\n"
            f"metric_hint={metric_hint}\n"
            "goal=근거 기반 학습 전략 추천"
        )

    def _section_hint(self, weak_section: str) -> str:
        mapping={
            "BACKGROUND": "문제 배경과 상황 이해",
            "GOAL": "문제 목표와 요구사항 파악",
            "RULE": "핵심 규칙과 로직 정리",
            "CONSTRAINT": "입력 범위, 시간 복잡도, 메모리 제한 확인",
        }
        return mapping.get(weak_section, weak_section)

    def _quiz_hint(self, weak_quiz:str) -> str:
        mapping={
            "ALGORITHM": "알고리즘 선택과 적용 근거",
            "LOGIC_CHECK": "조건 분기, 예외 처리, 반례 검증",
            "DATA_STRUCTURE": "적절한 자료구조 선택",
            "TIME_COMPLEXITY": "N 범위와 시간 복잡도 계산"
        }
        return mapping.get(weak_quiz, weak_quiz)

    def _metric_hint(self, weakest_metric: str) -> str:
        mapping = {
            "accuracy": "정답률과 요구사항 반영 정확도",
            "independence": "힌트 의존도와 자가 해결력",
            "efficiency": "풀이 속도와 시간 복잡도 적합성",
            "consistency": "학습 지속성과 반복 훈련",
        }
        return mapping.get(weakest_metric, weakest_metric)

    # TODO: 이거 뭐임?
    def _build_filter(self, weak_quiz:str) -> models.Filter | None:
        if weak_quiz == "DATA_STRUCTURE":
            return models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value="DATA_STRUCTURE"),
                    )
                ]
            )
        return None

report_rag_service = ReportRagService()
