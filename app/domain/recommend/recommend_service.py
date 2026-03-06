# 문제 추천 수식
from app.database.vector_db import vector_db


class RecommendService:
    def __init__(self):
        self.vector_db = vector_db

    # 초기 정적으로 문제 추천
    async def get_static_recomendations(
        self,
        user_level: str,
        solved_problem_ids: list[int],
        challenge_problem_ids: list[int],
        limit: int = 5,
    ):

        static_pool_by_level = {
            "newbie": [1, 22, 23, 24, 25, 26, 40],
            "pupil": [27, 28, 29, 30, 31, 11, 32],
            "specialist": [8, 33, 34, 35, 36, 37, 38, 39],
        }

        # 유저 레벨이 알 수 없는 값이라면 newbie로 지정
        pool = static_pool_by_level.get(user_level, static_pool_by_level["newbie"])
        # 이미 경험한 문제는 제외하여 추천하지 않음
        excluded = set(solved_problem_ids or []) | set(challenge_problem_ids or [])
        picked = [p_id for p_id in pool if p_id not in excluded][:limit]

        if not picked:
            return {"message": "추천 가능한 정적 문제가 없습니다."}
        return {
            "recommended_problem_ids": [str(p_id) for p_id in picked],
            "weak_tags": [],
            "reason_context": {
                "recommendation_type": "static",
                "starter_basis": "초기 사용자에게 기초 개념과 학습 흐름을 잡아줄 수 있는 문제를 우선 추천",
                "matched_tags": [],
                "similar_user_count": 0,
            },
        }

    async def get_collaborative_recommendations(
        self, user_id: int, current_problem_id: int, exclude_ids: list[int] = None, limit: int =5,
    ):
        # 1. 현재 사용자의 가장 최신 기억 가져오기
        user_memories, _ = self.vector_db.client.scroll(
            collection_name="User_memories",
            scroll_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
            limit=100,
            with_vectors=True,
            with_payload=True,
        )

        if not user_memories:
            print(f"❌ [DEBUG] 유저 {user_id}의 기억을 DB에서 찾을 수 없음")
            return {"message": "기록 없음"}

        target_memory = user_memories[0]
        target_vector = target_memory.vector
        target_payload = target_memory.payload or {}
        target_weak_tags = set(target_memory.payload.get("weak_tags", []))

        # 제외할 문제 목록 = 이미 푼 문제 + 현재 도전 중인 문제
        solved_problems = set(exclude_ids) if exclude_ids else set()
        solved_problems.update(target_memory.payload.get("recent_solved_ids", []))
        if current_problem_id:
            solved_problems.add(current_problem_id)

        # 2. 나와 유사한 실수를 한 '다른 유저' 5명 찾기
        similar_users = self.vector_db.client.query_points(
            collection_name="User_memories",
            query=target_vector,
            query_filter={
                "must_not": [{"key": "user_id", "match": {"value": user_id}}]
            },
            limit=30,
            with_payload=True,
        ).points

        print(f"🔍 [DEBUG] 유사 유저 검색 결과 수: {len(similar_users)}")

        if not similar_users:
            return {"message": "유사 유저 없음"}

        # 3. 추천 후보군 및 점수 계산
        candidate_scores: dict[int, float] = {}
        candidate_tag_matches: dict[int, set[str]] = {}

        for peer in similar_users:
            peer_payload = peer.payload or {}
            peer_solved = peer_payload.get("recent_solved_ids", [])
            print(f"   - 유사유저({peer.id})가 푼 문제들: {peer_solved}")

            peer_weak_tags = set(peer_payload.get("weak_tags", []))
            matched_tags = target_weak_tags.intersection(peer_weak_tags)
            matching_tags_count = len(matched_tags)


            for p_id in peer_solved:
                if p_id in solved_problems:
                    continue

                # 기본 1점 + 태그 매칭 가산점
                base_score = 1.0 + (matching_tags_count * 5.0)
                candidate_scores[p_id] = candidate_scores.get(p_id, 0.0) + base_score

                if p_id not in candidate_tag_matches:
                    candidate_tag_matches[p_id] = set()
                candidate_tag_matches[p_id].update(matched_tags)


        if not candidate_scores:
            return {"message": "추천 가능한 문제가 없습니다."}


        sorted_recommendations = sorted(
            candidate_scores.items(), key=lambda x: x[1], reverse=True
        )
        top_ids = [str(p_id) for p_id, score in sorted_recommendations[:limit]]

        all_matched_tags = set()
        for pid in top_ids:
            all_matched_tags.update(candidate_tag_matches.get(int(pid), set()))
        # top_problem_id = int(top_ids[0])
        # top_matched_tags = list(candidate_tag_matches.get(top_problem_id, set()))

        print(f"🎯 [DEBUG] 최종 추천 후보 리스트: {top_ids}")

        return {
            "user_id": user_id,
            "recommended_problem_ids": top_ids,
            "weak_tags": list(target_weak_tags),
            "reason_context": {
                "recommendation_type": "collaborative",
                "similar_user_count": len(similar_users),
                "matched_tags": list(all_matched_tags),
                "collaborative_basis": "비슷한 취약 태그와 풀이 패턴을 보인 사용자들이 해결한 문제를 기반으로 추천",
            },
        }


recommend_service = RecommendService()
