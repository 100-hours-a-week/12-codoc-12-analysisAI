import json
import re
from typing import Any
import hashlib
import asyncio

from openai import AsyncOpenAI, APITimeoutError

from app.core.config import settings


class RecommendLlmService:
    def __init__(self):
        self.base_url = settings.RECOMMEND_LLM_BASE_URL
        self.api_key = settings.RECOMMEND_LLM_API_KEY
        self.model = settings.RECOMMEND_LLM_MODEL
        self.timeout_sec = settings.RECOMMEND_LLM_TIMEOUT_SEC

        self.max_concurrency = settings.RECOMMEND_LLM_MAX_CONCURRENCY
        self.acquire_timeout_sec = settings.RECOMMEND_LLM_ACQUIRE_TIMEOUT_SEC
        self._llm_semaphore = asyncio.Semaphore(self.max_concurrency)

        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout_sec,)


    # 배치 로직
    async def generate_reasons_batch(
            self,
            *,
            scenario: str,
            user_level: str,
            items: list[dict[str,Any]],
    ) -> dict[int, str]:

        if not items:
            return {}

        reason_map: dict[int, str] = {}
        llm_items: list[dict[str, Any]] = []

        for item in items:
            problem_id = int(item["problem_id"])
            weak_tags = item.get("weak_tags", [])
            problem_payload = item.get("problem_payload")
            recommendation_context = item.get("recommendation_context", {}) or {}
            evidence_docs = item.get("evidence_docs", []) or []
            fallback_slot = item.get("fallback_slot")

            fallback = self._fallback_reason(
                scenario=scenario,
                weak_tags=weak_tags,
                recommendation_context=recommendation_context or {},
                problem_payload=problem_payload,
                problem_id=problem_id,
                fallback_slot=fallback_slot,
            )
            reason_map[problem_id] = self._force_exclamation(fallback)

            if not problem_payload:
                print("[DEBUG] problem_payload is None -> fallback")
                continue

            tags = problem_payload.get("tags", [])
            matched_tags = recommendation_context.get("matched_tags", [])
            focus_tags = weak_tags or matched_tags or tags[:2]

            ending_styles = [
                "정리해볼 수 있어요.",
                "점검해보면 좋아요.",
                "한 단계 더 안정적으로 다듬을 수 있어요.",
                "실수 패턴을 줄이는 데 유익합니다.",
                "학습 흐름을 잡는 데 적합해요!",
            ]
            style_hint = ending_styles[(fallback_slot or 0) % len(ending_styles)]

            compact_evidence = []
            for d in evidence_docs[:2]:
                if not isinstance(d, dict):
                    continue
                compact_evidence.append(
                    {
                        "paragraph_type": d.get("paragraph_type", ""),
                        "essential_summary": d.get("essential_summary", ""),
                        "essential_keywords": d.get("essential_keywords", []),
                        "chatbot_answer_guide": d.get("chatbot_answer_guide", ""),
                    }
                )
            llm_items.append(
                {
                    "problem_id": problem_id,
                    "title": problem_payload.get("title", ""),
                    "tags": tags,
                    "level": problem_payload.get("level", ""),
                    "summary": problem_payload.get("summary", ""),
                    "paragraph_type": problem_payload.get("paragraph_type", ""),
                    "essential_keywords": problem_payload.get("essential_keywords", []),
                    "chatbot_answer_guide": problem_payload.get("chatbot_answer_guide", ""),
                    "recommendation_type": recommendation_context.get("recommendation_type", ""),
                    "matched_tags": matched_tags,
                    "similar_user_count": recommendation_context.get("similar_user_count", 0),
                    "collaborative_basis": recommendation_context.get("collaborative_basis", ""),
                    "starter_basis": recommendation_context.get("starter_basis", ""),
                    "weak_tags": weak_tags,
                    "focus_tags": focus_tags,
                    "style_hint": style_hint,
                    "evidence_docs": compact_evidence,
                }
            )

        if not llm_items:
            return reason_map

        system_prompt = (
            "너는 코딩테스트 학습 서비스의 추천 사유 생성기다. "
            "최우선 목표는 사용자의 코딩테스트 문해력(문제 의도 파악, 조건 해석, 경계값 확인, 출력 형식 준수)을 "
            "향상시키는 관점에서 추천 이유를 명확히 전달하는 것이다. "
            "반드시 JSON 객체 하나만 출력하고, 최상위 키는 reasons 하나만 사용한다. "
            "reasons는 배열이며 각 원소는 problem_id(int), reason_msg(str)를 포함해야 한다. "
            "마크다운, 코드블록, 설명 문장, 여분 텍스트는 금지한다. "
            "문제의 스토리나 배경 상황을 길게 설명하지 말고, 학습 관점의 보완 포인트 중심으로 작성한다. "
            "수치 조건, 변수명, 수식, 복잡도 표기 같은 원문 세부사항을 직접 인용하지 않는다. "
            "알고리즘 명칭(DP, BFS, DFS, 투포인터, 이분탐색 등)도 직접 노출하지 않는다."
            "각 문제의 evidence_docs를 최우선 근거로 사용한다."
        )

        user_prompt = f"""
        [사용자 정보]
        - 시나리오: {scenario}
        - 사용자 레벨: {user_level}
        
        [추천 문제 목록] 
        {json.dumps(llm_items, ensure_ascii=False)}
        
        작성 목적:
        - 이 문제를 통해 사용자가 코딩테스트 문해력(문제 의도 파악, 조건/예외 해석, 출력 형식 점검)을
          어떤 관점에서 보완할 수 있는지 한 문장으로 설명한다.
            
        작성 규칙:
        1. 한국어 한 문장으로만 작성한다. (45~90자)
        2. 문제의 "읽기 포인트"를 반드시 반영한다.
           - 조건 해석 / 경계값 / 예외 케이스 / 출력 형식 / 핵심 로직 전개 중 최소 1개
        3. 사용자 취약 태그와 문제 포인트를 자연스럽게 연결한다.
        4. 각 문제의 evidence_docs에서 최소 1개 근거를 반영한다.
            - evidence_docs가 비어 있으면 title/tags/summary를 근거로 작성한다.
        5. 문제 정보(제목/태그/요약/핵심 키워드) 중 최소 1개를 내부적으로 참고하되,
           최종 문장은 문제 줄거리/배경 설명 없이 학습 포인트 중심으로 작성한다.
        6. 추천 방식별 톤 가이드를 따른다.
           - NEW: 문제 줄거리/제목/수치/고유명사 언급 금지, 학습 포인트 중심 문장만.
           - DAILY/ON_DEMAND: 보완 포인트 중심 톤, 실수 패턴 개선 관점 강조
        7. 협업 추천인 경우에도 "몇 명의 사용자가 풀었다" 같은 문장은 직접 쓰지 않는다.
        8. 다음 표현은 금지한다.
           - "추천한 문제예요"
           - "좋은 문제예요"
           - "도움이 돼요"
           - "이해를 높였어요"
           - "향상시켰어요"
           - "몇 명의 사용자가"
           - 문제 배경/스토리를 그대로 설명하는 문장
        9. 문체는 친절함 50, 전문성 50의 균형을 유지한다.
           - 부드러운 존댓말로 작성하되 학습 포인트는 구체적으로 제시한다.
           - 과장된 칭찬/감탄 표현은 사용하지 않는다.
           - 지나치게 어둡거나 단정적인 표현은 사용하지 않는다.
        10. 구체적이되 장황하지 않게, 서비스 문구처럼 간결하게 작성한다.
        11. 아래 예시는 참고만 하고 문장을 그대로 복사하지 않는다.
        12. 문제 원문의 세부 조건을 그대로 쓰지 않는다.
           - 금지: 숫자 범위(예: 10^5), 변수명(N, M), 수식/부등식, 복잡도 표기(O(N))
           - 권장: "조건 해석", "경계값 점검", "예외 처리", "출력 형식"처럼 추상화된 표현
        13. 알고리즘 이름을 직접 쓰지 않는다.
           - 금지: DP, BFS, DFS, 투포인터, 이분탐색, 슬라이딩 윈도우 등
           - 권장: "풀이 흐름", "로직 전개", "분기 처리", "예외 대응" 같은 표현
        14. 문장 끝맺음은 매번 다양하게 작성한다.
           - "문제예요.", "문제입니다."로만 반복 종료하지 않는다.
           - 이번 문장 권장 끝맺음 스타일: "{style_hint}"

        좋은 예시:
        - "조건 해석과 경계값 점검 기준을 정리하며 구현 정확도를 한 단계 높일 수 있어요."
        - "예외 케이스를 먼저 분리해보는 연습으로 로직 전개 안정성을 점검해보면 좋아요."
        - "출력 형식과 분기 순서를 함께 확인하며 실수 패턴을 줄이는 데 유익합니다."

        나쁜 예시:
        - "대기 시간을 고려한 마지막 소의 입장 시점을 계산하는 과정에서..."
        - "N, M <= 10^5 조건을 활용해..."
        - "O(N log N)으로 처리하며..."
        - "슬라이딩 윈도우와 투포인터를 활용해..."
        - "DP 배열을 구성해..."
        - "동전 조합을 누적해 가는 전개 방식을 익히면서..."
        - "비슷한 취약점을 가진 5명의 사용자들이 풀면서 이해를 높였어요."
        - "조건문과 구현 능력을 향상시켰어요."
        - "조건 해석을 보완하기 좋은 문제예요."
        - "출력 형식을 점검하기 좋은 문제입니다."
        
        반드시 아래 JSON만 반환:
        {{
          "reasons": [
            {{"problem_id":2, "reason_msg": "..."}},
            {{"problem_id":5, "reason_msg": "..."}}
            ]
        }}
        """.strip()

        # -- 세마포어 획득 --
        acquired = False
        try:
            await asyncio.wait_for(
                self._llm_semaphore.acquire(),
                timeout = self.acquire_timeout_sec,
            )
            acquired = True
        except asyncio.TimeoutError:
            print("[DEBUG] LLM semaphore acquire timeout -> fallback")
            return reason_map

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=900,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout = self.timeout_sec,
            )
            raw = response.choices[0].message.content or ""
            parsed = self._parse_json(raw)
            print("[DEBUG] LLM raw response:", raw)
            print("[DEBUG] parsed response:", parsed)

            rows = parsed.get("reasons")
            if not isinstance(rows, list):
                print("[DEBUG] batch reasons key missing -> fallback(all)")
                return reason_map

            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = row.get("problem_id")
                reason = row.get("reason_msg")

                try:
                    pid_int = int(pid)
                except Exception:
                    continue

                if pid_int not in reason_map:
                    continue

                if isinstance(reason, str) and reason.strip():
                    reason_map[pid_int] = self._force_exclamation(reason.strip())

            return reason_map

        except (APITimeoutError, TimeoutError) as e:
            print("[DEBUG] batch LLM timeout:", repr(e))
            print("[DEBUG] batch fallback reason:", repr(e))
            return reason_map
        except Exception as e:
            print("[DEBUG] batch LLM exception:", repr(e))
            return reason_map
        finally:
            if acquired:
                self._llm_semaphore.release()


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
            return self._force_exclamation(reason.strip())

        print("[DEBUG] reason_msg missing in parsed response -> fallback")
        return self._force_exclamation(fallback)

    def _force_exclamation(self, text: str) -> str:
        stripped = text.strip()
        # Keep output style consistent by forcing a single trailing exclamation mark.
        stripped = re.sub(r"[.!?~]+$", "", stripped)
        return f"{stripped}!"

    def _fallback_reason(
            self,
            *,
            scenario: str,
            weak_tags: list[str],
            recommendation_context: dict[str, Any],
            problem_payload: dict[str, Any] | None = None,
            problem_id: int | None = None,
            fallback_slot: int | None = None,
    ) -> str:
        recommendation_type = recommendation_context.get("recommendation_type", "")
        matched_tags = recommendation_context.get("matched_tags", [])
        focus_tags = weak_tags or matched_tags
        focus = ", ".join(focus_tags[:2]) if focus_tags else "핵심 개념"
        title = ""
        resolved_problem_id = problem_id
        if problem_payload:
            title = str(problem_payload.get("title", "") or "")
            payload_problem_id = problem_payload.get("problem_id")
            if isinstance(payload_problem_id, int):
                resolved_problem_id = payload_problem_id

        collaborative_templates = [
            f"유사한 풀이 패턴에서 자주 막히는 {focus}를 보완해볼 수 있어요.",
            f"비슷한 학습 흐름을 바탕으로 {focus}를 점검해보면 좋아요.",
            f"현재 단계에서 {focus}를 실전 풀이에 연결해보기에 알맞아요!",
            f"{focus} 관련 실수를 줄이는 연습으로 활용해보기 좋아요.",
        ]
        new_templates = [
            f"처음 학습할 때 필요한 {focus} 감각을 부담 없이 익힐 수 있어요!",
            f"입문 단계에서 {focus} 흐름을 정리해보기 좋아요.",
            f"{focus}를 처음 접할 때 기초를 다지는 데 적합해요.",
            f"기초 개념과 풀이 흐름을 함께 점검해보기에 좋아요!",
            f"초기 학습 단계에서 핵심 포인트를 안정적으로 정리할 수 있어요.",
        ]
        default_templates = [
            f"지금 학습 흐름에서 {focus}를 정교하게 다듬는 데 도움이 돼요.",
            f"현재 풀이 단계에서 {focus}를 다시 정리해볼 만해요.",
            f"{focus}를 중심으로 풀이 완성도를 높이는 데 효과적이에요.",
            f"최근 학습 패턴을 기준으로 보면 {focus}를 강화하기에 적절해요.",
        ]

        if recommendation_type == "collaborative":
            templates = collaborative_templates
        elif scenario == "NEW":
            templates = new_templates
        else:
            templates = default_templates

        if fallback_slot is not None:
            return templates[fallback_slot % len(templates)]

        if resolved_problem_id is not None:
            return templates[resolved_problem_id % len(templates)]

        seed = "|".join(
            [
                scenario or "",
                recommendation_type or "",
                ",".join(weak_tags or []),
                ",".join(matched_tags or []),
                recommendation_context.get("collaborative_basis", "") or "",
                recommendation_context.get("starter_basis", "") or "",
                title,
                ]
        )
        idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(templates)
        return templates[idx]

recommend_llm_service = RecommendLlmService()
