import json
import os
import uuid

from qdrant_client.http import models

from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service



def load_algo_concepts():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    concepts_path = os.path.join(
        base_dir, "app", "database", "algo_concepts", "algo_concepts.json"
    )
    collection_name = "Algo_Concepts"

    if not os.path.exists(concepts_path):
        print(f"❌ 파일을 찾을 수 없습니다: {concepts_path}")
        return

    collections = [c.name for c in vector_db.client.get_collections().collections]
    if collection_name not in collections:
        vector_db.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_db.vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"✅ 컬렉션 생성 완료: {collection_name}")

    with open(concepts_path, encoding="utf-8") as f:
        concepts = json.load(f)

    if not isinstance(concepts, list):
        print("❌ algo_concepts.json 형식이 list가 아닙니다.")
        return

    print(f"📦 {len(concepts)}개 concept 적재 시작...")

    for item in concepts:
        definition = item.get("definition", "")
        if not definition:
            print(f"⚠️ definition 비어있어서 스킵: {item.get('concept')}")
            continue

        vector = embedding_service.get_embedding(definition)

        concept = item.get("concept", "unknown")
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"algo:{concept}"))

        vector_db.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=item,
                )
            ],
        )

    print("🚀 Algo_concepts 적재 완료")

if __name__ == "__main__":
    load_algo_concepts()

# python3 -m scripts.load_algo_dataset
