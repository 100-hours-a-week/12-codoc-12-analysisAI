import json

from openai import AsyncOpenAI

from app.common.exceptions.custom_exception import OcrProcessingException, InvalidImageException
from app.core.config import settings
from app.domain.workbook.workbook_schemas import WorkbookQueueRequest, ProblemDetail

_SYSTEM_PROMPT = """당신은 코딩테스트 문제 전문 OCR 엔진입니다.

하나 이상의 이미지가 주어지면 다음을 수행하세요:
1. 이미지에 코딩테스트(알고리즘/프로그래밍) 문제가 포함되어 있는지 판단하세요.
2. 코딩테스트 문제가 맞다면, 문제 전체를 추출하여 다음 JSON 형식으로 반환하세요:
   {
     "is_coding_test": true,
     "title": "<문제 제목>",
     "content": "<마크다운 형식의 문제 본문 전체>"
   }
   content는 이미지에 등장하는 섹션을 모두 포함하여 아래 마크다운 구조를 따르세요:
   ## 문제
   ## 제약사항
   ## 입력
   ## 출력
   ## 예제 입력 N
   ## 예제 출력 N

3. 각 헤더 당 구분선을 포함하여 문제 본문 전체를 마크다운 형식으로 content에 담아 반환하세요.
[마크다운 예시]
## 문제
영선이는 BOJ 캠프의 강사다. 이번에 스위핑에 대한 세미나를 진행하였는데, 그 연습문제를 만들었다. “1사분면 정수 좌표계에 n개의 점이 주어질 때, 원점을 지나는 직선 중 직선위의 점들이 최대가 되는 직선에 대해, 그 점들의 개수를 구하여라”라 문제를 만들었지만, 나중에 보니 스위핑이 아닌 단순히 기울기로 만들어 개수를 세는 풀이의 허점이 존재하였다.

영선이는 스위핑으로 풀게 하기 위하여 급하게 점을 선분으로 문제를 바꾸었다. 따라서 수강생인 당신은 바뀐 문제를 풀면 된다.

“1사분면 정수 좌표계에 n개의 선분이 주어질 때, 원점을 지나는 직선 중 직선이 교차하는 선분이 최대가 되는 직선에 대해, 그 선분들의 개수를 구하여라”

---

## 입력
첫째 줄에는 선분의 개수 n이 주어진다.(1≤n≤100,000)
다음 n줄에는 선분의 두 점 좌표 x1, y1, x2, y2가 주어진다.(1≤x1, y1, x2, y2≤1,000,000,000) 선분의 두 점의 같은 경우는 없으며, 선분끼리 교차할 수도 있다.
(제한 사항 - 시간 제한: 2 초, 메모리 제한: 512 MB)

---

## 출력
교차하는 선분이 최대가 되는 직선에 대해, 그 선분들의 개수를 구하시오.

---

## 예제 입력 1
3
4 4 8 2
5 5 6 6
7 7 2 6

## 예제 출력 1
3
    
4. 코딩테스트 문제가 아니라면 다음을 반환하세요:
   { "is_coding_test": false }

반드시 유효한 JSON 객체만 반환하세요. 설명이나 마크다운 코드 블록(```)은 포함하지 마세요."""

_USER_PROMPT = "이미지에서 코딩테스트 문제를 추출해주세요."


class WorkbookService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.VLM_BASE_URL,
            api_key=settings.VLM_API_KEY,
            timeout=settings.VLM_TIMEOUT_SEC,
        )
        self.model = settings.VLM_MODEL

    async def extract_problem(self, req: WorkbookQueueRequest) -> ProblemDetail:
        image_contents = [
            {"type": "image_url", "image_url": {"url": str(img.url)}}
            for img in req.images
        ]
        image_contents.append({"type": "text", "text": _USER_PROMPT})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=4000,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": image_contents},
                ],
            )
        except Exception as exc:
            raise OcrProcessingException(f"OCR 모델 호출에 실패했습니다: {exc}") from exc

        raw = response.choices[0].message.content or ""
        return self._parse_ocr_result(raw)

    def _parse_ocr_result(self, raw: str) -> ProblemDetail:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OcrProcessingException(f"OCR 결과를 JSON으로 파싱할 수 없습니다: {exc}") from exc

        if not data.get("is_coding_test"):
            raise InvalidImageException()

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()

        if not title or not content:
            raise OcrProcessingException("OCR 결과에 title 또는 content가 누락되었습니다.")

        return ProblemDetail(title=title, content=content)


workbook_service = WorkbookService()
