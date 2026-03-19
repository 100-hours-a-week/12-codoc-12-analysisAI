# 파이썬 3.12 버전 환경
FROM python:3.12-slim

# 작업 폴더 설정
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 라이브러리 설치 (캐시 활용을 위해 requirements.txt만 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 현재 폴더의 모든 소스 코드를 복사
COPY . .

RUN chmod +x /app/scripts/run_api_and_worker.sh

# 서버/워커 실행
CMD ["/app/scripts/run_api_and_worker.sh"]
