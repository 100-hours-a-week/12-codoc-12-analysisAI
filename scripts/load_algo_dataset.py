import json
import os
import uuid

from qdrant_client.http import models

from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service



def load_algo_concepts():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    concepts_dir = os.path.join(base_dir, "app", "database", "algo_concepts")
    collection_name = "Algo_Concepts"

    if not os.path.isdir(concepts_dir):
        print(f"❌ 디렉터리를 찾을 수 없습니다: {concepts_dir}")
        return

    json_files = sorted(
        f for f in os.listdir(concepts_dir) if f.lower().endswith(".json")
    )
    if not json_files:
        print(f"❌ 적재할 JSON 파일이 없습니다: {concepts_dir}")
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

    total_upserted = 0

    for file_name in json_files:
        file_path = os.path.join(concepts_dir, file_name)
        with open(file_path, encoding="utf-8") as f:
            concepts = json.load(f)

        if not isinstance(concepts, list):
            print(f"⚠️ {file_name}: JSON 형식이 list가 아니어서 스킵")
            continue

        print(f"📦 {file_name}: {len(concepts)}개 concept 적재 시작...")
        file_upserted = 0

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
            file_upserted += 1

        total_upserted += file_upserted
        print(f"✅ {file_name}: {file_upserted}개 upsert 완료")

    print(f"🚀 Algo_concepts 적재 완료 (총 {total_upserted}개 upsert)")

if __name__ == "__main__":
    load_algo_concepts()

# python3 -m scripts.load_algo_dataset
