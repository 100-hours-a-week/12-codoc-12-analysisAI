import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sympy.physics.quantum.gate import normalized

from app.core.config import settings


class VectorDB:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
            https=False,
        )
        self.memory_collection = "User_memories"
        self.problem_collection = "Problems"
        self.vector_size = 1024

        self._init_memory_collection()

    def _init_memory_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]

        if self.memory_collection not in collections:
            self.client.create_collection(
                collection_name=self.memory_collection,
                vectors_config=models.VectorParams(
                    size=self.vector_size, distance=models.Distance.COSINE
                ),
            )
            print(f"✅ 전용 컬렉션 '{self.memory_collection}'이 준비됨.")

    # --- Problems 컬렉션 관련 기능 (Read Only) ---

    async def get_problem_by_id(self, problem_id: int):
        try:
            results, _ = self.client.scroll(
                collection_name=self.problem_collection,
                scroll_filter={
                    "must": [
                        {"key": "problem_id", "match": {"value": problem_id}}
                    ]
                },
                limit=1,
                with_payload=True,
            )
            return results[0].payload if results else None
        except Exception as e:
            print(f"❌ 문제 조회 에러 ({problem_id}): {e}")
            return None

    # --- user_memories 컬렉션 관련 기능 (Read & Write) ---

    def upsert_memory(self, user_id: int, problem_id: int, vector: list, payload: dict, point_id: str | None = None):
        payload.update({"user_id": user_id, "problem_id": problem_id})

        session_id = str(payload.get("session_id") or "").strip()

        if not session_id:
            raise ValueError("session_id is required")

        raw_key = point_id or f"user:{user_id}:problem:{problem_id}:session:{session_id}"
        stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, raw_key))

        self.client.upsert(
            collection_name=self.memory_collection,
            points=[
                models.PointStruct(id=stable_uuid, vector=vector, payload=payload)
            ],
        )

    async def search_memories(self, user_id: int, query_vector: list, limit: int = 5):
        return self.client.search(
            collection_name=self.memory_collection,
            query_vector=query_vector,
            # 특정 유저의 과거 오답 기록 중 현재와 유사한 것 검색 (해당 유저의 오답노트만 참고하도록 함)
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=user_id)
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )

    async def find_latest_memory_point_id(
        self,
        *,
        user_id:int,
        problem_id: int,
        session_id: str | None = None,
    ) -> Any | None:
        must_conditions: list[models.FieldCondition] = [
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
            models.FieldCondition(key="problem_id", match=models.MatchValue(value=problem_id)),
        ]
        if session_id:
            must_conditions.append(
                models.FieldCondition(key="session_id", match=models.MatchValue(value=session_id)),
            )

        rows, _ = self.client.scroll(
            collection_name=self.memory_collection,
            scroll_filter=models.Filter(must=must_conditions),
            limit=100,
            with_payload=True,
        )
        if not rows:
            return None

        latest = max(rows, key=lambda r: int((r.payload or {}).get("created_at", 0)))
        return latest.id

    @staticmethod
    def _weakest_metric_from_scores(scores: dict[str, float| int]) -> str:
        metric_map = {
            "accuracy_score": "ACCURACY",
            "independence_score": "INDEPENDENCE",
            "speed_score": "SPEED",
            "consistency_score": "CONSISTENCY",
        }
        weakest_key = min(metric_map.keys(), key=lambda k:float(scores.get(k,0)))
        return metric_map[weakest_key]

    async def update_memory_scores(
            self,
            *,
            user_id: int,
            problem_id: int,
            session_id: str | None,
            scores: dict[str, float | int],
    ) -> bool:
        point_id = await self.find_latest_memory_point_id(
            user_id=user_id,
            problem_id=problem_id,
            session_id=session_id,
        )
        if point_id is None:
            return False

        normalized_scores = {
            "accuracy_score": float(scores.get("accuracy_score", 0)),
            "independence_score": float(scores.get("independence_score", 0)),
            "speed_score": float(scores.get("speed_score", 0)),
            "consistency_score": float(scores.get("consistency_score", 0)),
        }
        metric = self._weakest_metric_from_scores(normalized_scores)

        self.client.set_payload(
            collection_name=self.memory_collection,
            payload={
                "metric_source": "REPORT",
                "metric": metric,
                "scores": normalized_scores,
            },
            points=[point_id],
        )
        return True

vector_db = VectorDB()
