import json
import os

from app.core.config import settings
from app.database.vector_db import vector_db
from app.services.embedding_service import embedding_service


def load_user_memories():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    users_dir = os.path.join(base_dir, "app", "database", "user_dataset")

    if not os.path.exists(users_dir):
        print(f"❌ 파일을 찾을 수 없습니다: {users_dir}")
        return

    json_files = [f for f in os.listdir(users_dir) if f.endswith(".json")]

    if not json_files:
        print("📁 처리할 JSON 파일이 없습니다.")
        return

    print(
        f"🧠 공유 DB({settings.QDRANT_HOST})에 총 {len(json_files)}개의 사용자 파일을 적재 시작..."
    )

    for file_name in json_files:
        file_path = os.path.join(users_dir, file_name)

        with open(file_path, encoding="utf-8") as f:
            user_data = json.load(f)

            items = user_data if isinstance(user_data, list) else [user_data]

            for item in items:
                error_summary = item.get("payload", {}).get("error_summary", "")
                if not error_summary:
                    print(f"⚠️ {file_name}: error_summary가 비어 있어 스킵")
                    continue

                vector = embedding_service.get_embedding(error_summary)
                raw_user_id = item.get("payload", {}).get("user_id")
                try:
                    user_id_int = int("".join(filter(str.isdigit, str(raw_user_id))))
                except ValueError:
                    user_id_int = 0

                full_payload = item.get("payload", {})
                problem_id = int(full_payload.get("problem_id"))
                session_id = str(full_payload.get("session_id") or "").strip()
                point_id = f"user:{user_id_int}:problem:{problem_id}:session:{session_id}"

                if not session_id:
                    print(f"{file_name}: session_id 누락으로 스킵")
                    continue

                vector_db.upsert_memory(
                    user_id=user_id_int,
                    problem_id=problem_id,
                    vector=vector,
                    payload=full_payload,
                    point_id=point_id,
                )
        print(f"   ✅ 파일 '{file_name}' 내 유저 데이터 적재 완료")

    print("\n🚀 데이터셋 로드 프로세스 완료")


if __name__ == "__main__":
    load_user_memories()

# python3 -m scripts.load_dataset
