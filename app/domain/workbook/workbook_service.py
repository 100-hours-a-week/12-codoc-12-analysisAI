from openai import AsyncOpenAI

from app.common.exceptions.custom_exception import OcrProcessingException
from app.core.config import settings
from app.domain.workbook.workbook_schemas import ImageSubmitReq, ImageSubmitRes


class WorkbookService:
    def __init__(self):
        self.base_url = settings.OCR_LLM_BASE_URL
        self.api_key = settings.OCR_LLM_API_KEY
        self.model = settings.OCR_LLM_MODEL
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def extract_text(self, req: ImageSubmitReq) -> ImageSubmitRes:
        recognized_text = await self._extract_text_from_image(str(req.images[0].url))
        return ImageSubmitRes(recognized_text=recognized_text)

    async def _extract_text_from_image(self, image_url: str) -> str:
        request_url = f"{self.base_url.rstrip('/')}/chat/completions"
        print("[OCR] base_url:", self.base_url)
        print("[OCR] request_url:", request_url)
        print("[OCR] model:", self.model)
        print("[OCR] image_url:", image_url)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=2000,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an OCR engine. Extract only the text visible in the image. "
                            "Do not summarize, explain, translate, or add labels. "
                            "Preserve line breaks when they are meaningful."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all visible text from this image."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
            )
        except Exception as exc:
            print("[OCR] request failed:", repr(exc))
            raise OcrProcessingException(
                f"OCR 처리 중 외부 모델 호출에 실패했습니다: {exc}"
            ) from exc

        content = response.choices[0].message.content or ""
        normalized_text = self._normalize_text(content)

        if not normalized_text:
            raise OcrProcessingException("이미지에서 인식된 텍스트가 없습니다.")

        return normalized_text

    def _normalize_text(self, content: str) -> str:
        text = content.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()

        return text


workbook_service = WorkbookService()
