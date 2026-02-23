import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models

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
            result = self.client.retrieve(
                collection_name=self.problem_collection,
                ids=[problem_id],
                with_payload=True,
            )
            return result[0].payload if result else None
        except Exception as e:
            print(f"❌ 문제 조회 에러 ({problem_id}): {e}")
            return None

    # --- user_memories 컬렉션 관련 기능 (Read & Write) ---

    def upsert_memory(self, user_id: int, problem_id: int, vector: list, payload: dict):
        payload.update({"user_id": user_id, "problem_id": problem_id})

        self.client.upsert(
            collection_name=self.memory_collection,
            points=[
                models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload)
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


vector_db = VectorDB()
