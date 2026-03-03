import json
import os
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


class RecommendLlmService:
    def __init__(self):
        self.base_url = settings.RECOMMEND_LLM_BASE_URL
        self.api_key = settings.RECOMMEND_LLM_API_KEY
        self.model = settings.RECOMMEND_LLM_MODEL

        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def generate_reason(self, *, scenario:str, user_level:str, weak_tags:list[str], problem_payload: dict[str, Any] | None, recommendation_context: dict[str, Any] | None = None) -> str:
        fallback = self._fallback_reason(scenario=scenario, weak_tags=weak_tags, recommendation_context=recommendation_context or {},)

        if not problem_payload:
            print("[DEBUG] problem_payload is None -> fallback")
            return fallback

        recommendation_context = recommendation_context or {}

        title = problem_payload.get("title", "")
        tags = problem_payload.get("tags", [])
        level = problem_payload.get("level", "")
        summary = problem_payload.get("summary", "")

        recommendation_type = recommendation_context.get("recommendation_type", "")
        matched_tags = recommendation_context.get("matched_tags", [])
        similar_user_count = recommendation_context.get("similar_user_count", 0)
        collaborative_basis = recommendation_context.get("collaborative_basis", "")
        starter_basis = recommendation_context.get("starter_basis", "")

        # TODO : 프롬프트 엔지니어링 고도화 필요
        system_prompt = (
            "너는 알고리즘 학습 서비스의 추천 사유 작성기다. "
            "사용자에게 보여줄 추천 사유를 한국어로 자연스럽고 전문적으로 작성해야 한다. "
            "반드시 JSON 객체만 출력해야 하며, 마크다운, 코드블록, 설명 문장은 금지한다. "
            '반환 키는 "reason_msg" 하나만 사용한다.'
        )

        user_prompt = f"""
        [사용자 정보]
        - 시나리오: {scenario}
        - 사용자 레벨: {user_level}
        - 취약 태그: {weak_tags}
        
        [추천 문제 정보]
        - 제목: {title}
        - 태그: {tags}
        - 난이도: {level}
        - 문제 요약: {summary}
        
        [추천 근거]
        - 추천 방식: {recommendation_type}
        - 겹치는 취약 태그: {matched_tags}
        - 유사 사용자 수: {similar_user_count}
        - 협업 추천 근거: {collaborative_basis}
        - 초기 추천 근거: {starter_basis}
        
        작성 목적:
        - 이 문제가 왜 현재 사용자에게 필요한지 한눈에 이해되도록 추천 사유를 작성한다.
        
        작성 규칙:
        1. 추천 사유는 반드시 한국어 한 문장으로 작성한다.
        2. 55자 이상 95자 이하로 작성한다.
        3. 문제의 제목, 태그, 요약 중 최소 1개를 반드시 반영한다.
        4. 사용자 취약 태그와 이 문제가 연결되는 지점을 자연스럽게 설명한다.
        5. 협업 추천인 경우에도 "몇 명의 사용자가 풀었다" 같은 문장은 직접 쓰지 않는다.
        6. "비슷한 풀이 패턴", "유사한 어려움", "취약 개념 보완" 등의 표현은 사용할 수 있지만,
           문제 자체의 학습 포인트를 중심으로 문장을 구성한다.
        7. 아래와 같은 표현은 금지한다.
           - "이 문제를 통해 향상시켰어요"
           - "이해를 높였어요"
           - "추천한 문제예요"
           - "몇 명의 사용자가"
        8. 문장은 서비스 문구처럼 자연스럽고 구체적으로 작성한다.
        9. 문제의 핵심 풀이 포인트가 드러나도록 작성한다.
        10. 아래 JSON 형식만 반환한다.
        
        좋은 예시:
        - "피보나치 수의 점화식과 초기값 처리 흐름을 다시 점검하며 동적 계획법의 기본을 다질 수 있는 문제예요."
        - "동전 조합을 누적해 가는 전개 방식을 익히면서 조건 분기와 DP 흐름을 함께 정리할 수 있어요."
        - "득표 수를 비교하며 최소 이동 횟수를 계산하는 과정에서 구현과 조건 처리 감각을 점검하기 좋은 문제예요."
        
        나쁜 예시:
        - "비슷한 취약점을 가진 5명의 사용자들이 풀면서 이해를 높였어요."
        - "조건문과 구현 능력을 향상시켰어요."
        - "추천한 문제예요."
        
        반환 형식:
        {{
          "reason_msg": "..."
        }}
        """.strip()

        try:
            print("[DEBUG] LLM request model:", self.model)
            print("[DEBUG] LLM request base_url:", self.base_url)
            print("[DEBUG] LLM request title:", title)
            print("[DEBUG] LLM request tags:", tags)
            print("[DEBUG] LLM request weak_tags:", weak_tags)
            print("[DEBUG] LLM request context:", recommendation_context)

            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content or ""
            parsed = self._parse_json(raw)
            print("[DEBUG] LLM raw response:", raw)
            print("[DEBUG] parsed response:", parsed)

            result = self._sanitize_reason(parsed, fallback)
            print("[DEBUG] final reason_msg:", result)

            return result
        except Exception as e:
            print("[DEBUG] LLM exception type:", type(e).__name__)
            print("[DEBUG] LLM exception detail:", repr(e))
            print("[DEBUG] fallback reason:", fallback)
            return fallback


    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()

        try:
            return json.loads(raw)
        except Exception:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            print("[DEBUG] JSON regex match failed")
            return {}

        try:
            return json.loads(match.group(0))
        except Exception as e:
            print("[DEBUG] JSON parse failed from regex block:", repr(e))
            return {}


    def _sanitize_reason(self, parsed: dict[str, Any], fallback:str) -> str:
        reason = parsed.get("reason_msg")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()

        print("[DEBUG] reason_msg missing in parsed response -> fallback")
        return fallback

    def _fallback_reason(self, *, scenario:str, weak_tags: list[str], recommendation_context: dict[str, Any],) -> str:
        recommendation_type = recommendation_context.get("recommendation_type", "")
        matched_tags = recommendation_context.get("matched_tags", [])

        if recommendation_type == "collaborative":
            if matched_tags:
                return (
                    f"비슷한 풀이 패턴을 보인 사용자들이 해결한 문제 중 "
                    f"{', '.join(matched_tags[:2])} 보완에 도움이 될 문제예요."
                )
            if weak_tags:
                return (
                    f"유사한 어려움을 겪은 사용자들의 풀이 흐름을 바탕으로 "
                    f"{', '.join(weak_tags[:2])} 보완에 맞춰 추천한 문제예요."
                )
            return "비슷한 풀이 패턴을 보인 사용자들의 학습 흐름을 바탕으로 추천한 문제예요."

        if scenario == "NEW":
            return "초기 학습 흐름을 잡고 핵심 개념을 점검하기 좋도록 추천한 문제예요."
        return "사용자의 취약 태그와 유사한 학습 패턴을 바탕으로 추천한 문제예요."

recommend_llm_service = RecommendLlmService()