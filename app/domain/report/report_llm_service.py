import json
import os
import re
from typing import Any

from openai import AsyncOpenAI
from app.common.observability.metrics import (
    LLM_COST_PER_REQUEST_USD,
    LLM_COST_TOTAL_USD,
    LLM_TOKENS_TOTAL,
)
from app.core.config import settings

class ReportLlmService:
    def __init__(self):
        self.base_url = settings.REPORT_LLM_BASE_URL
        self.api_key = settings.REPORT_LLM_API_KEY
        self.model = settings.REPORT_LLM_MODEL

        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def generate_sections(self, *, user_level:str, report_mode:str, growth_index:float, weak_section:str, weak_quiz:str, weakest_metric:str, present_growth: dict[str,float], evidence_docs: list[dict[str,Any]]) -> dict[str,str]:
        fallback = self._fallback_texts(
            report_mode=report_mode,
            weakest_metric=weakest_metric,
            weak_section=weak_section,
            weak_quiz=weak_quiz,
        )


        if report_mode == "WARM_UP":
            return fallback

        system_prompt = (
            "너는 코딩 학습 분석 리포트를 작성하는 코치다. "
            "반드시 JSON 객체만 출력해야 한다. "
            "마크다운, 코드블록, 설명 문장 없이 JSON만 반환한다. "
            "필수 키는 summary_comment, analysis_text, strategy_tip, recommended_action 이다. "
            "전체 톤은 밝고 따뜻하되, 지나치게 감성적이지 않고 전문적인 서비스 문구처럼 작성한다. "
            "사용자의 부족함을 단정적으로 표현하지 않는다. "
            "특히 summary_comment는 사용자의 성장 흐름을 긍정적으로 짚어주면서도 과장되지 않게 작성한다."
        )

        evidence_text = "\n".join(
            [
                f"- concept={d.get('concept','UNKNOWN')}"
                f"definition={d.get('definition','')},"
                f"core_logic={d.get('core_logic','')}"
                f"check_points={d.get('check_points',[])}"
                for d in evidence_docs[:3]
            ]
        ) or "-없음"

        user_prompt = f"""
            user_level={user_level}
            growth_index={growth_index}
            weak_section={weak_section}
            weak_quiz={weak_quiz}
            weakest_metric={weakest_metric}
            present_growth={present_growth}
            evidence_docs:
            {evidence_text}
            
            작성 규칙:
            1. 전체 톤은 밝음 70, 전문성 30 정도의 균형으로 작성한다.
            2. 교육적이고 따뜻한 톤을 유지하되, 지나치게 감성적이거나 유아적인 표현은 피한다.
            3. weak_section, weak_quiz, weakest_metric 중 최소 1개는 직접 언급한다.
            4. 각 문장은 1~2문장 이내로 작성한다.
            5. 사용자의 약점을 단정하거나 부정적으로 평가하지 않는다.
            6. 아래와 같은 표현은 금지한다.
               - "~이 부족합니다"
               - "~이 부족한 것 같습니다"
               - "~을 못하고 있습니다"
               - "~이 약합니다"
            7. summary_comment는 리포트의 첫인상 역할을 하도록, 밝고 안정감 있게 작성한다.
            8. summary_comment는 "노력하고 있어요"처럼 평이한 표현보다,
               "좋은 흐름이 보이고 있어요", "성장 방향이 점점 선명해지고 있어요",
               "풀이 감각이 조금씩 안정적으로 자리잡고 있어요",
               "이번 주에는 한 단계 더 정리된 풀이 흐름이 보이고 있어요"
               같은 표현을 활용한다.
            9. summary_comment는 응원하는 느낌은 주되, 과장된 칭찬이나 감탄사는 사용하지 않는다.
            10. analysis_text는 사용자를 평가하는 문장이 아니라,
                현재 반복되는 학습 패턴과 보완 포인트를 설명하는 문장으로 작성한다.
            11. strategy_tip, recommended_action은 바로 실천 가능한 문장으로 작성한다.
            12. 아래 JSON 키만 반환한다.
            
            좋은 예시:
            {{
              "summary_comment": "이번 주에는 풀이를 정리해가는 흐름이 더 또렷해지면서, 학습 방향이 한층 안정적으로 잡혀가고 있어요.",
              "analysis_text": "STRATEGY 문단에서 풀이 전개를 정리하는 과정이 조금 흔들리는 패턴이 보여, 시간 복잡도 기준을 먼저 세우는 연습이 도움이 될 수 있어요.",
              "strategy_tip": "문제를 읽은 뒤 바로 코드를 쓰기보다, 먼저 목표 시간복잡도를 한 줄로 적어보세요.",
              "recommended_action": "이번 주에는 시간 복잡도 판단이 필요한 문제를 2개 골라 풀이 전에 O(...)를 먼저 써보세요."
            }}
            
            나쁜 예시:
            {{
              "summary_comment": "이번 주에는 문제 해결 과정에서의 일관성 향상을 위해 노력하고 있어요.",
              "analysis_text": "전략 섹션에서 약점을 보이고 있으며, 특히 시간 복잡도에 대한 이해가 부족한 것 같습니다.",
              "strategy_tip": "더 열심히 하세요.",
              "recommended_action": "복습하세요."
            }}
            
            반환 형식:
            {{
              "summary_comment": "...",
              "analysis_text": "...",
              "strategy_tip": "...",
              "recommended_action": "..."
            }}
            """.strip()


        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=400,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            self._record_usage_metrics(response)
            raw = response.choices[0].message.content or ""
            parsed = self._parse_json(raw)
            print("[DEBUG] LLM base_url:", self.base_url)
            print("[DEBUG] LLM model:", self.model)

            return self._sanitize(parsed, fallback)
        except Exception:
            return fallback

    def _record_usage_metrics(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return

        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens

        LLM_TOKENS_TOTAL.labels(service="report", token_type="prompt").inc(prompt_tokens)
        LLM_TOKENS_TOTAL.labels(service="report", token_type="completion").inc(completion_tokens)
        LLM_TOKENS_TOTAL.labels(service="report", token_type="total").inc(total_tokens)

        cost_usd = (
            (prompt_tokens * settings.LLM_INPUT_TOKEN_PRICE_PER_MILLION_USD)
            + (completion_tokens * settings.LLM_OUTPUT_TOKEN_PRICE_PER_MILLION_USD)
        ) / 1_000_000

        LLM_COST_TOTAL_USD.labels(service="report").inc(cost_usd)
        LLM_COST_PER_REQUEST_USD.labels(service="report").observe(cost_usd)

    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except Exception:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


    def _sanitize(self, parsed: dict[str, Any], fallback: dict[str,str]) -> dict[str,str]:
        keys = ["summary_comment", "analysis_text", "strategy_tip", "recommended_action"]
        result: dict[str, str] = {}
        for key in keys:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
            else:
                result[key] = fallback[key]

        return result

    # TODO : WARMUP이랑 STANDARD 멘트 다시 수정!
    def _fallback_texts(self, *, report_mode:str, weakest_metric:str, weak_section:str, weak_quiz:str,) -> dict[str, str]:
        if report_mode == "WARM_UP":
            return {
                "summary_comment": "",
                "analysis_text": "",
                "strategy_tip": "",
                "recommended_action": "",
            }
        return {
            "summary_comment": f"이번 주 핵심 보완 지표는 {weakest_metric}입니다.",
            "analysis_text": f"{weak_section} 문단과 {weak_quiz} 유형에서 취약 패턴이 보입니다.",
            "strategy_tip": f"{weak_section} 문단을 먼저 읽고 {weak_quiz} 유형을 집중 복습해보세요.",
            "recommended_action": "문제 시작 전에 목표 시간복잡도를 정하고 풀이를 시작해보세요.",
        }

report_llm_service = ReportLlmService()
