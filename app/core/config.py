# 환경변수 및 설정
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME : str = "CodoC-AI"
    VERSION : str = "2.0.0"
    API_PREFIX : str = "/api/v2"

    # --- Vector DB (Qdrant) 설정 ---
    QDRANT_HOST : str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY : Optional[str] = None

    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # .env 파일을 읽어오기 위한 설정
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # S3 + llm 모델 추가 예정

settings = Settings()
