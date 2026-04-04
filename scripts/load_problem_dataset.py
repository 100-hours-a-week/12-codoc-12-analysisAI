import json
import os
import uuid

from qdrant_client.http import models

from app.core.config import settings
from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service
from app.database.postgres_client import postgres_client

PROBLEM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app",
    "database",
    "problem_dataset",
)


def ensure_problem_collection():
    existing = [c.name for c in vector_db.client.get_collections().collections]
    if vector_db.problem_collection not in existing:
        vector_db.client.create_collection(
            collection_name=vector_db.problem_collection,
            vectors_config=models.VectorParams(
                size=vector_db.vector_size,
                distance=models.Distance.COSINE,
            ),
        )

def load_problem_dataset():
    if not os.path.isdir(PROBLEM_DIR):
        print(f"❌ 문제 데이터셋 디렉터리({PROBLEM_DIR})가 없습니다.")
        return

    ensure_problem_collection()

    json_files = sorted(p for p in os.listdir(PROBLEM_DIR) if p.endswith(".json"))
    if not json_files:
        print("📁 적재할 problem JSON이 없습니다.")
        return

    print(f"📦 Qdrant({settings.QDRANT_HOST}:{settings.QDRANT_PORT})에 {len(json_files)}개 파일 적재 시작...")

    for file_name in json_files:
        file_path = os.path.join(PROBLEM_DIR, file_name)
        with open(file_path, encoding="utf-8") as f:
            payload = json.load(f)

        problems = payload if isinstance(payload,list) else [payload]
        print(f"  ➤ '{file_name}'에 {len(problems)}개 문제")

        for problem in problems:
            problem_id = int(problem["problem_id"])
            answer_guides = problem.get("answer_guides", [])
            for idx, paragraph in enumerate(answer_guides, start =1):
                text = (
                    paragraph.get("content")
                    or paragraph.get("essential_summary")
                    or paragraph.get("chatbot_answer_guide")
                )
                if not text:
                    print(f"    ⚠️ paragraph {paragraph.get('paragraph_type')}에 내용 없음, 건너뜀")
                    continue

                vector = embedding_service.get_embedding(text)
                payload_point = {
                    "problem_id": problem_id,
                    "title": problem.get("title"),
                    "difficulty": problem.get("difficulty"),
                    "problem_algorithm_tag": problem.get("problem_algorithm_tag",[]),
                    "paragraph_type": paragraph.get("paragraph_type"),
                    "paragraph_order": idx,
                    "content": paragraph.get("content"),
                    "essential_summary": paragraph.get("essential_summary"),
                    "essential_keywords": paragraph.get("essential_keywords",[]),
                    "chatbot_answer_guide": paragraph.get("chatbot_answer_guide"),
                }
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"problem:{problem_id}:{paragraph.get('paragraph_type')}:{idx}"))

                vector_db.client.upsert(
                    collection_name=vector_db.problem_collection,
                    points=[
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload_point,
                        )
                    ],
                )

        print(f"    ✅ '{file_name}' 처리 완료")
    print("🚀 문제 데이터셋 Qdrant 적재 완료")

if __name__ == "__main__":
    load_problem_dataset()
