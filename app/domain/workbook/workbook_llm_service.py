import json

import google.generativeai as genai

from app.common.exceptions.custom_exception import (
    InvalidProblemContentException,
    SummaryGenerationException,
    ContentVerificationException,
)
from app.core.config import settings
from app.domain.workbook.workbook_schemas import ProblemDetail, SummaryCard, Quiz

# ──────────────────────────────────────────────
# Stage 0: 문제 내용 유효성 검증 프롬프트
# ──────────────────────────────────────────────
_CONTENT_VALIDATION_PROMPT_BASE = """당신은 코딩 테스트 문제의 기술적 정합성을 검증하는 전문가입니다.

[중요 전제]
아래 문제 텍스트는 사용자가 촬영한 이미지를 Vision-Language 모델(vLM)이 OCR 처리한 결과입니다.
따라서 다음과 같은 상황이 발생할 수 있습니다:
- 사진이 잘려 일부 내용이 누락된 경우
- OCR 인식 오류로 숫자·수식·기호가 부정확하게 추출된 경우
- 여러 장의 이미지가 합쳐지며 순서가 뒤섞인 경우

이러한 한계를 감안하여, 명백한 오류가 있을 때에만 INVALID로 판단하십시오.
사소한 오탈자나 경미한 인식 오류는 VALID로 허용하십시오.

[검증 항목]
1. 문제 설명 논리 일관성: 문제 본문이 자체적으로 논리적으로 일관성이 있는가? (명백히 모순된 조건, 불완전한 정의 등)
2. 입출력 예시 정합성: 문제 설명의 규칙을 입력 예시에 적용했을 때 출력 예시와 기술적으로 일치하는가?
3. 콘텐츠 충분성: 요약카드와 퀴즈를 생성하기에 충분한 내용(문제 본문, 제약 조건, 입출력 예시)이 포함되어 있는가?

[출력 규칙]
- 3가지 항목 모두 통과 시: "VALID" 한 단어만 출력.
- 명백한 문제 발견 시: "INVALID: <구체적인 이유>" 형식으로 출력.

[입력 문제]
"""

# ──────────────────────────────────────────────
# Stage 1: 콘텐츠 생성 프롬프트
# ──────────────────────────────────────────────
_GENERATION_PROMPT_BASE = """[역할]
당신은 코딩 테스트 교육 플랫폼 'CodoC'의 콘텐츠 생성 전문가입니다.
주어진 코딩 테스트 문제(Markdown)를 분석하여, 학습자의 독해력을 점검하는 요약 카드(Summary Card)와 기술적 이해도를 평가하는 퀴즈(Quiz) 데이터를 JSON 형식으로 생성해야 합니다.

[목표]
1. 요약 카드: 긴 문제 지문을 [배경] - [목표] - [규칙] - [제약사항] 순서로 구조화하여, 올바른 요약문을 완성하는 객관식 문제를 만듭니다.
2. 퀴즈: 알고리즘, 논리, 자료구조, 시간복잡도 4가지 영역에서 기술적으로 검증된 4지 선다형 퀴즈를 만듭니다.

[핵심 규칙: 정답 위치 랜덤화]
절대 정답을 항상 첫 번째(0번 인덱스)에 고정하지 마십시오.
모든 선택지(choices)는 정답 1개와 오답 3개로 구성하되, 반드시 무작위로 섞어야(Shuffle) 합니다.
answer_index는 섞인 배열 내에서 실제 정답이 위치한 인덱스(0~3)를 정확하게 가리켜야 합니다.

[1. 요약 카드(Summary Card) 작성 규칙]
요약 카드는 문제의 긴 텍스트를 핵심만 추려내는 독해력 점검 도구입니다.
아래 4가지 paragraph_type 순서로 카드를 구성하십시오.

paragraph_type 별 작성 가이드:
- BACKGROUND (배경): 문제의 세계관이나 데이터의 성격(예: 2차원 격자, 게임 레벨) 요약.
- GOAL (목표): 최종적으로 구해야 하는 값(정답)의 정의.
- RULE (규칙): 데이터를 처리하는 핵심 로직(예: 이동 규칙, 점수 계산법).
- CONSTRAINT (제약 사항): N의 크기나 시간/메모리 제한.

선택지(choices) 생성 규칙:
오답은 알고리즘 문제에서 흔히 볼 수 있지만 이 문제에는 해당하지 않는 내용이어야 합니다.
(예: 정렬 문제가 아닌데 "오름차순 정렬", 그래프가 아닌데 "최단 경로" 등)

[2. 퀴즈(Quiz) 작성 규칙]
반드시 아래 4가지 quiz_type 순서를 지키십시오 (sequence: 1~4).
1. ALGORITHM: 적합한 알고리즘 기법 (예: 그리디, DP, BFS, 구현)
2. LOGIC_CHECK: 특정 입력값이 주어졌을 때의 정확한 결과값 (구체적 예시)
3. DATA_STRUCTURE: 효율적인 자료구조나 엣지 케이스 처리 방법
4. TIME_COMPLEXITY: 입력 크기 N에 따른 시간 복잡도

해설(explanation) 작성 톤앤매너:
- "챗봇입니다", "제 생각에는" 금지. 전공 서적처럼 건조하고 명확한 기술적 문체 사용.
- 정답인 이유를 논리적 근거(제약 조건, 알고리즘 특성 등)를 들어 설명.

[JSON 출력 포맷]
반드시 아래 구조만 반환하세요. 마크다운 코드 블록이나 설명은 포함하지 마세요.
{
  "summary_card": [
    {
      "paragraph_type": "BACKGROUND",
      "paragraph_order": 1,
      "answer_index": 2,
      "choices": ["(오답1)", "(오답2)", "(정답)", "(오답3)"]
    },
    {
      "paragraph_type": "GOAL",
      "paragraph_order": 2,
      "answer_index": 1,
      "choices": ["(오답1)", "(정답)", "(오답2)", "(오답3)"]
    },
    {
      "paragraph_type": "RULE",
      "paragraph_order": 3,
      "answer_index": 3,
      "choices": ["(오답1)", "(오답2)", "(오답3)", "(정답)"]
    },
    {
      "paragraph_type": "CONSTRAINT",
      "paragraph_order": 4,
      "answer_index": 0,
      "choices": ["(정답)", "(오답1)", "(오답2)", "(오답3)"]
    }
  ],
  "quiz": [
    {
      "quiz_type": "ALGORITHM",
      "question": "질문 내용",
      "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
      "answer_index": 2,
      "explanation": "기술적 해설",
      "sequence": 1
    },
    {
      "quiz_type": "LOGIC_CHECK",
      "question": "질문 내용",
      "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
      "answer_index": 0,
      "explanation": "기술적 해설",
      "sequence": 2
    },
    {
      "quiz_type": "DATA_STRUCTURE",
      "question": "질문 내용",
      "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
      "answer_index": 1,
      "explanation": "기술적 해설",
      "sequence": 3
    },
    {
      "quiz_type": "TIME_COMPLEXITY",
      "question": "질문 내용",
      "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
      "answer_index": 3,
      "explanation": "기술적 해설",
      "sequence": 4
    }
  ]
}

[입력 데이터]
"""

# ──────────────────────────────────────────────
# Stage 2: 검수 프롬프트
# ──────────────────────────────────────────────
_VERIFICATION_PROMPT_BASE = """[역할]
당신은 코딩 테스트 교육 콘텐츠의 기술적 정합성(Technical Integrity)을 검증하고, 학습자의 눈높이에 맞춰 학습 경험(Learning Experience)을 설계하는 전문가입니다.
생성된 JSON(summary_card, quiz)이 문제 원문의 제약 조건을 정확히 반영했는지, 그리고 교육적으로 적절한지 비판적으로 검증해야 합니다.

[검수 가이드라인]
다음 5가지 섹션을 순서대로 수행하며 결함을 찾아내십시오.

1. 태그 및 용어 표준화
- 태그 준수: ALGORITHM, DATA_STRUCTURE 퀴즈의 답안이 아래 [허용 태그 리스트]에 포함되는지 확인. (리스트 외 용어는 오류 처리)
[허용된 태그 리스트]
수학, 구현, 다이나믹 프로그래밍, 자료구조(집합과 맵, 해시를 사용한 집합과 맵, 트리를 사용한 집합과 맵, 세그먼트 트리, 느리게 갱신되는 세그먼트 트리, 분리 집합, 우선순위 큐, 스택, 큐, 희소 배열, 연결 리스트, 덱), 그래프 이론, 그리디 알고리즘, 문자열, 브루트포스 알고리즘, 정렬, 애드 혹, 트리, 이분 탐색, 해 구성하기, 누적 합, 많은 조건 분기, 비트마스킹, 기하학, 스위핑, 매개 변수 탐색, 분할 정복, 두 포인터, 재귀, 슬라이딩 윈도우, 중간에서 만나기, 오프라인 쿼리, 좌표 압축, 해싱, 홀짝성, 제곱근 분할법, 게임 이론, 순열 사이클 분할
- 용어 표준성: 설명(explanation)에 사용된 용어가 CS 전공 서적의 표준 용어인지 확인.

2. 알고리즘 적합성 및 기술 검증 (Logic & Fact Check)
- Over-engineering 방지: 문제의 제약 조건(N) 대비 알고리즘이 적절한가?
  N ≤ 100: 단순 구현/완전 탐색 권장. (복잡한 자료구조/알고리즘 제안 시 경고)
  N ≥ 100,000: O(N log N) 이하 알고리즘 필수. (O(N^2) 제안 시 오류)
- Fact Check: 퀴즈의 정답과 해설이 수학적/논리적으로 100% 참인가? 계산 오류나 로직 비약이 없는지 확인.

3. 퀴즈의 범위 및 정답 검증 (Scope & Fact Check)
- Fact Check: quiz의 answer_index가 가리키는 정답이 기술적으로 100% 참(True)인지 검증.
- Scope Check: 퀴즈가 문제를 푸는 데 필수적인 개념을 묻는지 확인. 문제 풀이와 무관한 지나치게 지엽적인 내용을 묻는다면 코멘트.

4. 요약 카드 문맥 검증 (Contextual Fit)
summary_card의 choices 정답을 실제 문맥에 대입했을 때 한국어 조사의 호응과 내용이 자연스러운지 확인.

5. 난이도별 할루시네이션 패턴 정밀 검수 (Difficulty Pattern)
문제의 난이도를 상/중/하로 판단하고, 해당 레벨의 고질적인 오류를 집중 점검.
(상) 고난이도: 점화식의 논리적 오류, 시간 복잡도 제약 무시 여부.
(중) 중난이도: 지문의 세부 조건(예외 조항, 엣지 케이스)이 누락되었는지.
(하) 저난이도: 해설이 동어반복이나 당연한 소리를 하는지.

[출력 리포트 형식]
수정할 사항이 전혀 없다면 "ALL PASS"만 출력.
결함 발견 시 아래 양식 사용:
1. 태그 및 용어 검수 - 상태: [PASS / FAIL / WARNING]
2. 기술적 적합성 검수 - 상태: [PASS / FAIL / WARNING]
3. 퀴즈 범위 및 정답 검증 - 상태: [PASS / FAIL / WARNING]
4. 문맥 정합성 검수 - 상태: [PASS / FAIL]
5. 난이도별 패턴 정밀 검수 - 판단된 난이도: [상/중/하], 상태: [PASS / FAIL]

[입력 데이터]
1. 문제 원문
"""


_VALID_PARAGRAPH_TYPES = {"BACKGROUND", "GOAL", "RULE", "CONSTRAINT"}
_VALID_QUIZ_TYPES = {"ALGORITHM", "LOGIC_CHECK", "DATA_STRUCTURE", "TIME_COMPLEXITY"}


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
        await self._call_verification(problem, raw_json)
        return summary_cards, quizzes

    async def _call_content_validation(self, problem: ProblemDetail) -> None:
        prompt = _CONTENT_VALIDATION_PROMPT_BASE + f"제목: {problem.title}\n\n{problem.content}"
        try:
            response = await self._verify_model.generate_content_async(prompt)
        except Exception as exc:
            raise InvalidProblemContentException(f"Gemini 내용 검증 호출 실패: {exc}") from exc

        result = (response.text or "").strip()
        if not result.startswith("VALID"):
            reason = result.removeprefix("INVALID:").strip()
            raise InvalidProblemContentException(f"문제 내용이 유효하지 않습니다: {reason}")

    async def _call_generation(self, problem: ProblemDetail) -> str:
        prompt = _GENERATION_PROMPT_BASE + f"제목: {problem.title}\n\n{problem.content}"
        try:
            response = await self._gen_model.generate_content_async(prompt)
        except Exception as exc:
            raise SummaryGenerationException(f"Gemini 콘텐츠 생성 호출 실패: {exc}") from exc
        return response.text or ""

    async def _call_verification(self, problem: ProblemDetail, generated_json: str) -> None:
        prompt = (
            _VERIFICATION_PROMPT_BASE
            + f"제목: {problem.title}\n\n{problem.content}\n\n"
            + f"2. 생성된 JSON\n{generated_json}"
        )
        try:
            response = await self._verify_model.generate_content_async(prompt)
        except Exception as exc:
            raise ContentVerificationException(f"Gemini 검수 호출 실패: {exc}") from exc

        result = (response.text or "").strip()
        if "ALL PASS" not in result:
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
            if card.paragraph_type not in _VALID_PARAGRAPH_TYPES:
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
            if quiz.quiz_type not in _VALID_QUIZ_TYPES:
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
