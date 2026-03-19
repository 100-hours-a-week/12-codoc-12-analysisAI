import json
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
        self.timeout_sec = settings.REPORT_LLM_TIMEOUT_SEC

        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key or "EMPTY", timeout=self.timeout_sec, max_retries=0,)

    async def generate_sections(
            self, *, user_level:str,
            report_mode:str,
            growth_index:float,
            weak_section:str,
            weak_quiz:str,
            weakest_metric:str,
            present_growth: dict[str,float],
            paragraph_fail_stats: dict[str, int],
            quiz_fail_stats: dict[str, int],
            weakness_summary: dict[str, Any],
            evidence_docs: list[dict[str,Any]]
    ) -> dict[str,str]:
        fallback = self._fallback_texts(
            report_mode=report_mode,
            weakest_metric=weakest_metric,
            weak_section=weak_section,
            weak_quiz=weak_quiz,
        )


        if report_mode == "WARM_UP":
            return fallback

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            user_level=user_level,
            growth_index=growth_index,
            weak_section=weak_section,
            weak_quiz=weak_quiz,
            weakest_metric=weakest_metric,
            present_growth=present_growth,
            paragraph_fail_stats=paragraph_fail_stats,
            quiz_fail_stats=quiz_fail_stats,
            weakness_summary=weakness_summary,
            evidence_docs=evidence_docs,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.4,
                max_tokens=420,
                timeout=self.timeout_sec,
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

    def _build_system_prompt(self) -> str:
        return (
            "너는 코딩 학습 분석 리포트 코치다.\n"
            "반드시 JSON 객체만 반환한다.\n"
            "허용 키는 정확히 4개: summary_comment, analysis_text, strategy_tip, recommended_action\n\n"
            "작성 규칙:\n"
            "1) 각 값은 한국어 1~2문장, 짧고 명확하게 작성한다.\n"
            "2) 사용자 비난/단정 금지.\n"
            "2-1) 문체는 반드시 존댓말을 사용하고, 톤은 친절함 50 / 전문성 50의 균형을 유지한다.\n"
            "3) 쉬운 표현만 사용한다. 복잡도 표기(O(...)), 수식, 변수명 인용 금지.\n"
            "4) weak_section, weak_quiz, weakest_metric 중 최소 2개를 반영한다.\n"
            "5) paragraph_fail_stats, quiz_fail_stats, evidence_docs를 근거로 작성한다.\n"
            "6) 개인 이름 하드코딩 금지.\n"
            "7) 금지 표현: '부족합니다', '못하고 있습니다', '약합니다', '더 열심히 하세요'.\n"
            "8) 금지 표현 추가: '~ 부족해보입니다', '~ 어려움을 겪고 있습니다', '실수가 많아', '떨어집니다' 같은 부정 평가 문장 금지.\n"
            "9) 문장 구조는 반드시 '관찰 1문장 + 실행 행동 1문장'으로 작성한다.\n"
            "10) 관찰 문장은 현재 상태를 중립적으로 설명하고, 개선 가능성을 함께 제시한다.\n"
            "11) 금지 표현이 떠오르면 반드시 긍정적 학습 표현으로 바꿔 쓴다.\n"
            "   예: '일관성이 떨어집니다' -> '일관성은 학습 리듬을 만들수록 더 빠르게 올라갈 수 있어요'\n"
            "12) 최종 출력 전 자기 점검: 금지 표현이 1개라도 있으면 전체 문장을 다시 작성한다.\n"
            "13) strategy_tip은 2단계 행동으로 작성한다. (예: 1) ... 2) ...)\n"
            "14) recommended_action은 길게 쓰지 말고, 기간/횟수가 보이는 짧은 실천 과제로 작성한다.\n"
            "15) 문장 안에서 쉼표(,)를 과하게 사용하지 않는다. 가능하면 짧은 문장으로 끊어 쓴다.\n"
            "16) '정확도는 높지만 ~', '~지만 일관성이 낮다' 같은 부정 대조 문장 금지.\n"
            "17) 모든 문장은 '현재 강점 또는 진행 상태'를 먼저 언급하고, 이어서 '다음 행동'을 제시한다.\n"
            "18) analysis_text와 summary_comment는 희망적이고 전문적인 코칭 문장으로 작성한다.\n"
            "19) JSON 외 텍스트/코드블록/마크다운 금지.\n"
        )

    def _build_user_prompt(
            self, *,
            user_level: str,
            growth_index: float,
            weak_section: str,
            weak_quiz: str,
            weakest_metric: str,
            present_growth: dict[str, float],
            paragraph_fail_stats: dict[str, int],
            quiz_fail_stats: dict[str, int],
            weakness_summary: dict[str, Any],
            evidence_docs: list[dict[str, Any]],
    )-> str:
        section_ko = {
            "BACKGROUND": "배경 이해",
            "GOAL": "문제 목표 파악",
            "RULE": "규칙 해석",
            "CONSTRAINT": "제약조건 해석",
            "INSIGHT": "핵심 아이디어 정리",
            "STRATEGY": "풀이 전략 설계",
        }.get(weak_section,weak_section)

        quiz_ko = {
            "ALGORITHM": "알고리즘 선택",
            "LOGIC_CHECK": "로직 점검",
            "DATA_STRUCTURE": "자료구조 선택",
            "TIME_COMPLEXITY": "시간 복잡도 판단",
        }.get(weak_quiz, weak_quiz)

        metric_ko = {
            "accuracy": "정확도",
            "independence": "독립성",
            "efficiency": "속도",
            "consistency": "일관성",
        }.get(weakest_metric, weakest_metric)

        evidence_text = self._format_evidence_docs(evidence_docs)

        return f"""
        
        입력 데이터:
        - user_level: {user_level}
        - growth_index: {growth_index}
        - weak_section: {weak_section} ({section_ko})
        - weak_quiz: {weak_quiz} ({quiz_ko})
        - weakest_metric: {weakest_metric} ({metric_ko})
        - present_growth: {present_growth}
        - paragraph_fail_stats: {paragraph_fail_stats}
        - quiz_fail_stats: {quiz_fail_stats}
        - weakness_summary: {weakness_summary}
        
        근거 데이터:
        {evidence_text}
        
        출력 목적:
        - summary_comment: 이번 주 학습 흐름 요약
        - analysis_text: 반복 실수 패턴 + 원인 설명
        - strategy_tip: 바로 실행 가능한 2단계 방법
        - recommended_action: 짧고 측정 가능한 이번 주 실천 과제 1개
        
        반드시 아래 JSON만 반환:
        {{
          "summary_comment": "...",
          "analysis_text": "...",
          "strategy_tip": "...",
          "recommended_action": "..."
        }}
        """.strip()

    def _format_evidence_docs(self, evidence_docs:list[dict[str, Any]]) -> str:
        if not evidence_docs:
            return "- 없음"

        lines = []
        for d in evidence_docs[:3]:
            lines.append(
                f"- concept={d.get('concept', 'UNKNOWN')}, "
                f"definition={d.get('definition', '')}, "
                f"core_logic={d.get('core_logic', '')}, "
                f"check_points={d.get('check_points', [])}"
            )
        return "\n".join(lines)

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
        text = (raw or "").strip()
        if not text:
            return {}

        try:
            return json.loads(text)
        except Exception:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except Exception:
                pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
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
                result[key] = value.strip().replace("\n", " ")[:260]
            else:
                result[key] = fallback[key]

        return result

    def _fallback_texts(self, *, report_mode:str, weakest_metric:str, weak_section:str, weak_quiz:str,) -> dict[str, str]:
        metric_label = {
            "accuracy": "정확도",
            "independence": "독립성",
            "efficiency": "속도",
            "consistency": "일관성",
        }.get(weakest_metric, "핵심 지표")

        section_label = {
            "BACKGROUND": "배경 이해",
            "GOAL": "문제 목표 파악",
            "RULE": "규칙 해석",
            "CONSTRAINT": "제약조건 해석",
            "INSIGHT": "핵심 아이디어 정리",
            "STRATEGY": "풀이 전략 설계",
        }.get(weak_section, weak_section)

        quiz_label = {
            "ALGORITHM": "알고리즘 선택",
            "LOGIC_CHECK": "로직 점검",
            "DATA_STRUCTURE": "자료구조 선택",
            "TIME_COMPLEXITY": "시간 복잡도 판단",
        }.get(weak_quiz, weak_quiz)
        
        if report_mode == "WARM_UP":
            return {
                "summary_comment": "아직은 데이터가 쌓이는 단계예요! 이번 리포트는 첫 주 학습 방향을 잡아주는 가이드 중심으로 제공됩니다.",
                "analysis_text": "문제를 읽을 때 핵심 조건을 먼저 표시하는 습관을 만들면 다음 리포트 정확도가 크게 올라갑니다.",
                "strategy_tip": "문제마다 3단계로 진행해보세요. 1) GOAL/CONSTRAINT 밑줄 표시 2) 예상 시간 복잡도 한 줄 메모 3) 풀이 후 틀린 이유 1줄 기록",
                "recommended_action": "이번 주 2문제 이상 풀이를 목표로, 문제별 오답 원인을 한 줄씩 남겨보세요.",
            }
        return {
            "summary_comment": f"이번 주에는 '{metric_label}'을(를) 다듬으면 전체 풀이 안정성이 한 단계 올라갈 수 있어요.",
            "analysis_text": (
                f"기록을 보면 '{section_label}' 단계와 '{quiz_label}' 판단 구간에서 같은 유형의 실수가 반복되고 있어요. "
                "이 두 지점을 함께 점검하면 오답률을 효과적으로 줄일 수 있어요."
            ),
            "strategy_tip": (
                f"이번 주에는 문제를 읽을 때 먼저 '{section_label}'를 체크하고, "
                f"풀이를 시작하기 전에 '{quiz_label}' 기준을 한 줄로 정리해보세요."
            ),
            "recommended_action": (
                f"이번 주에는 '{metric_label}' 보완을 목표로 문제 2개를 연속 풀이하고, "
                "틀린 이유를 한 줄씩 기록해보세요."
            ),
        }

report_llm_service = ReportLlmService()
