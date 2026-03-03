# 환경변수 및 설정

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CodoC-AI"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v2"

    # --- Vector DB (Qdrant) 설정 ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None

    # Report LLM
    REPORT_LLM_BASE_URL: str = "http://localhost:8001/v1"
    REPORT_LLM_API_KEY: str = "EMPTY"
    REPORT_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"

    # Recommend LLM
    RECOMMEND_LLM_BASE_URL: str = "http://localhost:8001/v1"
    RECOMMEND_LLM_API_KEY: str = "EMPTY"
    RECOMMEND_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"

    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # .env 파일을 읽어오기 위한 설정
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
