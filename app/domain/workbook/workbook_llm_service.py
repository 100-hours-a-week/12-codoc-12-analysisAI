import json

import google.generativeai as genai

from app.common.exceptions.custom_exception import (
    InvalidProblemContentException,
    SummaryGenerationException,
    ContentVerificationException,
)
from app.core.config import settings
from app.domain.workbook.workbook_prompts import (
    CONTENT_VALIDATION_PROMPT_BASE,
    GENERATION_PROMPT_BASE,
    VERIFICATION_PROMPT_BASE,
    FIX_PROMPT_BASE,
    VALID_PARAGRAPH_TYPES,
    VALID_QUIZ_TYPES,
)
from app.domain.workbook.workbook_schemas import ProblemDetail, SummaryCard, Quiz


class WorkbookLlmService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._gen_model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )
        self._verify_model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )

    async def generate(self, problem: ProblemDetail) -> tuple[list[SummaryCard], list[Quiz]]:
        await self._call_content_validation(problem)

        raw_json = await self._call_generation(problem)
        summary_cards, quizzes = self._parse_generation(raw_json)

        try:
            await self._call_verification(problem, raw_json)
            return summary_cards, quizzes
        except ContentVerificationException as e:
            failure_detail = e.message

        fixed_json = await self._call_fix(problem, raw_json, failure_detail)
        summary_cards, quizzes = self._parse_generation(fixed_json)
        await self._call_verification(problem, fixed_json)
        return summary_cards, quizzes

    async def _call_content_validation(self, problem: ProblemDetail) -> None:
        prompt = CONTENT_VALIDATION_PROMPT_BASE + f"제목: {problem.title}\n\n```\n{problem.content}\n```"
        try:
            response = await self._verify_model.generate_content_async(prompt)
        except Exception as exc:
            raise InvalidProblemContentException(f"Gemini 내용 검증 호출 실패: {exc}") from exc

        result = (response.text or "").strip()
        if result.startswith("```"):
            lines = result.splitlines()
            inner = "\n".join(lines[1:-1]).strip()
            result = inner if inner else result
        if "INVALID" in result and "VALID" not in result:
            reason = result[result.find("INVALID"):].removeprefix("INVALID:").strip()
            raise InvalidProblemContentException(f"문제 내용이 유효하지 않습니다: {reason}")

    async def _call_fix(self, problem: ProblemDetail, generated_json: str, failure_detail: str) -> str:
        prompt = (
            FIX_PROMPT_BASE
            + f"제목: {problem.title}\n\n```\n{problem.content}\n```\n\n"
            + f"[생성된 JSON]\n{generated_json}\n\n"
            + f"[검수 실패 내용]\n{failure_detail}"
        )
        try:
            response = await self._gen_model.generate_content_async(prompt)
        except Exception as exc:
            raise SummaryGenerationException(f"Gemini 콘텐츠 수정 호출 실패: {exc}") from exc
        return response.text or ""

    async def _call_generation(self, problem: ProblemDetail) -> str:
        prompt = GENERATION_PROMPT_BASE + f"제목: {problem.title}\n\n{problem.content}"
        try:
            response = await self._gen_model.generate_content_async(prompt)
        except Exception as exc:
            raise SummaryGenerationException(f"Gemini 콘텐츠 생성 호출 실패: {exc}") from exc
        return response.text or ""

    async def _call_verification(self, problem: ProblemDetail, generated_json: str) -> None:
        prompt = (
            VERIFICATION_PROMPT_BASE
            + f"제목: {problem.title}\n\n```\n{problem.content}\n```\n\n"
            + f"2. 생성된 JSON\n{generated_json}"
        )
        try:
            response = await self._verify_model.generate_content_async(prompt)
        except Exception as exc:
            raise ContentVerificationException(f"Gemini 검수 호출 실패: {exc}") from exc

        result = (response.text or "").strip()
        if "상태: FAIL" in result or "- FAIL" in result:
            raise ContentVerificationException(f"콘텐츠 검수 실패:\n{result}")

    def _parse_generation(self, raw: str) -> tuple[list[SummaryCard], list[Quiz]]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SummaryGenerationException(
                f"Gemini 결과를 JSON으로 파싱할 수 없습니다: {exc}"
            ) from exc

        summary_cards_raw = data.get("summary_card") or []
        quizzes_raw = data.get("quiz") or []

        if not summary_cards_raw or not quizzes_raw:
            raise SummaryGenerationException(
                "요약카드 또는 퀴즈 생성 결과가 비어 있습니다. 문제 내용이 충분하지 않습니다."
            )

        try:
            summary_cards = [SummaryCard(**card) for card in summary_cards_raw]
            quizzes = [Quiz(**quiz) for quiz in quizzes_raw]
        except Exception as exc:
            raise SummaryGenerationException(
                f"Gemini 결과의 데이터 형식이 올바르지 않습니다: {exc}"
            ) from exc

        self._validate_structure(summary_cards, quizzes)
        return summary_cards, quizzes

    def _validate_structure(self, summary_cards: list[SummaryCard], quizzes: list[Quiz]) -> None:
        for card in summary_cards:
            if card.paragraph_type not in VALID_PARAGRAPH_TYPES:
                raise SummaryGenerationException(
                    f"요약카드 paragraph_type이 올바르지 않습니다: {card.paragraph_type}"
                )
            if not card.choices:
                raise SummaryGenerationException("요약카드 choices가 비어 있습니다.")
            if not (0 <= card.answer_index < len(card.choices)):
                raise SummaryGenerationException(
                    f"요약카드 answer_index({card.answer_index})가 choices 범위를 벗어났습니다."
                )

        for quiz in quizzes:
            if quiz.quiz_type not in VALID_QUIZ_TYPES:
                raise SummaryGenerationException(
                    f"퀴즈 quiz_type이 올바르지 않습니다: {quiz.quiz_type}"
                )
            if len(quiz.choices) != 4:
                raise SummaryGenerationException("퀴즈 선택지는 정확히 4개여야 합니다.")
            if not (0 <= quiz.answer_index < len(quiz.choices)):
                raise SummaryGenerationException(
                    f"퀴즈 answer_index({quiz.answer_index})가 choices 범위를 벗어났습니다."
                )


workbook_llm_service = WorkbookLlmService()
