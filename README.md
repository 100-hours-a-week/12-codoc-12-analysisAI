# 🐨 CodoC-Analysis-AI

학습자의 풀이 이력과 오답 패턴을 바탕으로 다음 문제를 추천하고, 학습 데이터를 분석해 개인화 리포트를 생성하는 FastAPI 기반 AI 서버입니다.  
- **문제 추천** : 사용자 상태와 풀이 이력을 바탕으로 다음 문제 추천 
- **분석 리포트** : 주간 학습 로그와 취약 패턴을 바탕으로 성장 리포트 생성 
- **나만의 문제 만들기** : 업로드된 문제 이미지에서 문제를 추출하고 요약카드/퀴즈 생성

&nbsp;


## 1. 폴더 구조

```text
.
├── app                              # 애플리케이션 메인 소스
│   ├── main.py
│   ├── core                         # 전역 설정/환경변수 관리
│   │   └── config.py
│   ├── common                       # 공통 응답/예외 처리
│   │   ├── api_response.py
│   │   ├── exceptions                    # 커스텀 예외 및 예외 핸들러
│   │   │   ├── base_exception.py
│   │   │   ├── custom_exception.py
│   │   │   └── exception_handler.py
│   │   └── observability                 # 로깅/메트릭/트레이싱
│   │       ├── logging_config.py
│   │       ├── metrics.py
│   │       └── tracing.py
│   ├── domain                       # 비즈니스 도메인 로직
│   │   ├── recommend                # 문제 추천 도메인
│   │   │   ├── recommend_router.py        # 추천 API 라우터
│   │   │   ├── recommendation_schemas.py  # 추천 요청/응답 스키마
│   │   │   ├── recommend_usecase.py       # 추천 흐름 오케스트레이션
│   │   │   ├── recommend_service.py       # 정적/협업 추천 계산
│   │   │   └── recommend_llm_service.py   # 추천 사유 LLM 생성
│   │   ├── report                   # 분석 리포트 도메인
│   │   |   ├── report_router.py           # 리포트 API 라우터
│   │   |   ├── report_schemas.py          # 리포트 요청/응답 스키마
│   │   |   ├── report_service.py          # 지표 계산/리포트 조립
│   │   |   ├── report_rag_service.py      # RAG 근거 조회
│   │   |   ├── report_llm_service.py      # 리포트 문구 LLM 생성
│   │   └── workbook                  # 워크북 OCR/콘텐츠 생성 도메인
│   │       ├── workbook_service.py
│   │       ├── workbook_llm_service.py
│   │       ├── workbook_prompts.py
│   │       └── workbook_schemas.py
│   ├── database                     # DB 클라이언트/데이터셋
│   │   ├── vector_db.py
│   │   ├── problem_dataset          # 문제 메타/가이드 원천 데이터
│   │   ├── algo_concepts            # 리포트 RAG 근거 데이터
│   │   └── user_dataset             # 협업 추천용 유저 메모리 데이터
│   ├── services                     # 공용 서비스 레이어
│   │   └── embedding_service.py
│   ├── queue                        
│   │   ├── constants.py             # 큐/익스체인지 이름 정의
│   │   └── rabbitmq.py              # RabbitMQ 연결 관리
│   └── workers                      # 비동기 작업 소비자
│       ├── ai_worker.py                  # 추천/리포트 비동기 워커
│       └── ocr_worker.py                 # 워크북 OCR 비동기 워커
├── scripts                          # 초기 데이터 적재/셋업 스크립트
│   ├── load_problem_dataset.py
│   ├── load_algo_dataset.py
│   ├── load_user_dataset.py
│   ├── run_api_and_worker.sh             # API + worker 동시 실행
│   └── monitoring
│       ├── start_analysis_exporters.sh   # analysis 서버 exporter 실행
│       └── stop_analysis_exporters.sh    # analysis 서버 exporter 중지
├── monitoring                            # Prometheus/Grafana/Loki/Tempo/Alertmanager 구성
│   ├── docker-compose.monitoring.yml
│   ├── analysis-exporters.compose.yml
│   ├── prometheus
│   ├── alertmanager
│   ├── loki
│   ├── tempo
│   └── deploy-scripts
├── codedeploy                       # CodeDeploy 배포 스크립트
├── docker-compose.yml               # API 컨테이너 실행 정의
├── Dockerfile                       # API 이미지 빌드 정의
├── pyproject.toml
├── requirements.txt                 # 파이썬 의존성 목록
└── README.md
```

&nbsp;

## 2. 상세 기능 설명
문제 추천/ 분석 리포트는 HTTP 라우터가 노출 되어있지만 RabbitMQ 기반 비동기 워커 파이프라인으로 동작

<br>

### 2-1. 문제 추천 (`/api/v2/recommend`)
- 사용자 레벨, 시나리오, 이미 푼 문제를 기반으로 문제를 추천
- 추천 결과에는 단순 문제 ID만이 아니라 왜 이 문제를 지금 풀어야하는지에 대한 설명 포함

**추천 흐름 요약:**
1. `NEW` 시나리오: 레벨별 정적 추천 풀에서 5개 추천
2. `DAILY`, `ON_DEMAND`: Qdrant `User_memories` 기반 협업 추천
3. 협업 추천 결과가 5개 미만이면 정적 추천으로 부족분 보완
4. 각 문제에 대해 LLM으로 `reason_msg` 생성

### 2-2. 분석 리포트 (`/api/v2/reports`)
- 주간 학습 로그와 정답/오답 통계를 기반으로 성장 리포트를 생성
- 리포트는 '현재 학습 상태 요약', '최근 취약 지점 분석', '성장 포인트 진단', '다음 학습 방향 제안'과 같은 내용 포함

**리포트 흐름 요약:**
1. `solved_problems_weekly < 3`이면 `WARM_UP`
2. 정확도/독립성/효율성/일관성 지표 계산
3. 취약 항목에 맞는 근거 문서를 RAG로 조회
4. 근거 + 지표를 LLM에 전달해 최종 리포트 문구 생성


### 2-3. 나만의 문제 만들기(워크북) OCR (`api/v2/ocr`)
1. 이미지 URL 목록을 입력으로 수신
2. vLM으로 이미지에서 원문 텍스트 추출 
3. 코딩테스트 문제 여부 판단 및 문제 본문 구조화 
4. Gemini 기반으로 요약 카드와 퀴즈 생성 
5. 결과를 MQ 응답 메시지로 발행

### 2-4. 비동기 워커 (`app/workers/ai_worker.py`)
- RabbitMQ 요청 큐를 소비해 추천/리포트/OCR을 비동기로 처리합니다.
- **요청 큐** : `recommend.request.q`, `report.request.q`, `custom.problem.request`
- **응답 큐** : `recommend.response.q`, `report.response.q`, `custom.problem.response`
- `custom.problem.exchange`

&nbsp;

## 3. 기술 스택

- **Backend** : `FastAPI`, `Uvicorn`
- **Queue** : `RabbitMQ`, `aio-pika`
- **Vector DB** : `Qdrant`
- **Embedding** : `BAAI/bge-m3` (`FlagEmbedding`)
- **LLM** :  
   - **추천/리포트** : `Qwen-2.5-32B-Instruct`
   - **OCR** : `Qwen2.5-VL-7B-Instruct`
   - **워크북 카드/퀴즈 생성** : `gemini-2.0-flash`
- **Observability** :
   - `Prometheus`, `Grafana`, `Alertmanager`, `Loki`, `Tempo`, `OpenTelemetry`


&nbsp;

## 4. 빠른 실행 가이드 (로컬)

### 4-1. 사전 준비
- **Python `3.12`**
- Qdrant, RabbitMQ, 추천/리포트용 LLM endpoint, OCR용 Vision LLM endpoint, Gemini API Key

**테스트용으로 빠르게 띄울 때:**

```bash
# Qdrant (앱 기본 포트 6444에 맞춰 매핑)
docker run -d --name qdrant -p 6444:6333 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant

# RabbitMQ
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 4-2. 설치
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4-3. 환경 변수 (`.env`)
.env.template 참고

### 4-4. 초기 데이터 적재 (최초 1회 권장)
데이터셋은 별도로 필요
```bash
python -m scripts.load_problem_dataset
python -m scripts.load_algo_dataset
python -m scripts.load_user_dataset
```

### 4-5. 서버 실행
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4-6. 워커 실행 (선택)
```bash
python -m app.workers.ai_worker
python -m app.workers.ocr_worker
```
**한 번에 실행**
```bash
sh scripts/run_api_and_worker.sh
```

### 4-7. 헬스체크
- `GET /` : 서버 상태
- `GET /health/db` : qdrant 서버 연결 상태

### 4-8. Docker Compose 실행 
```bash
docker compose up --build
```

&nbsp;


## 5. API 요약
기본 엔드포인트 
- `GET /` : 서버 상태 확인 
- `GET /health/db` : Qdrant 연결 상태 확인 
- `GET /metrics` : Prometheus 메트릭 수집 엔드포인트 

공통 응답 포맷:
```json
{
  "code": "SUCCESS",
  "message": "OK",
  "data": {}
}
```

<br>

### 5-1. 추천 API
- `POST /api/v2/recommend`

요청 예시:
```json
{
  "user_id": 1,
  "user_level": "newbie",
  "scenario": "NEW",
  "filter_info": {
    "solved_problem_ids": [1, 2],
    "challenge_problem_ids": [3]
  }
}
```

응답 예시:
```json
{
  "code": "SUCCESS",
  "message": "OK",
  "data": {
    "user_id": 1,
    "scenario": "NEW",
    "recommendations": [
      {
        "problem_id": 22,
        "reason_msg": "..."
      }
    ]
  }
}
```

주의:
- `scenario=NEW`는 `solved_problem_ids` 개수 3 미만일 때만 허용됩니다.

### 5-2. 리포트 API
- `POST /api/v2/reports`

요청 예시:
```json
{
  "user_id": 1,
  "user_level": "newbie",
  "analysis_period": {
    "start_date": "2026-03-01",
    "end_date": "2026-03-07"
  },
  "raw_metrics": {
    "chatbot_msg_history": [],
    "total_chatbot_requests": 5,
    "solve_duration_sec": 1800,
    "solved_problems_weekly": 4
  },
  "paragraph_fail_stats": {
    "GOAL": 2,
    "CONSTRAINT": 1
  },
  "quiz_fail_stats": {
    "TIME_COMPLEXITY": 2
  }
}
```

### 5-3. 워크북 OCR API 
요청 예시: 
```json
{
  "customProblemId": 123,
  "images": [
    {
      "order": 1,
      "url": "https://example.com/problem-page-1.png"
    },
    {
      "order": 2,
      "url": "https://example.com/problem-page-2.png"
    }
  ]
}
```

응답 예시: 
```json
{
  "customProblemId": 123,
  "response": {
    "code": "SUCCESS",
    "message": "문제 분석이 완료되었습니다.",
    "data": {
      "problem_detail": {
        "title": "문제 제목",
        "content": "## 문제\n..."
      },
      "summary_card": [],
      "quiz": []
    }
  }
}
```

<br> 

## 6. 모니터링 
**<구성 디렉터리>**
- `monitoring/` : 모니터링 서버용 compose 및 설정 
- `scripts/monitoring/` : analysis 서버 exporter 실행/중지 스크립트
- `codedeploy/monitoring/` : 배포 번들용 모니터링 설정 

<br>

로컬에서 exporter 실행 
```bash
./scripts/monitoring/start_analysis_exporters.sh
```
GPU 서버라면 
```bash
./scripts/monitoring/start_analysis_exporters.sh --gpu
```
중지 
```bash
./scripts/monitoring/stop_analysis_exporters.sh
```

<br>

## 7. 참고사항 
- 추천/리포트는 FastAPI API로 노출되어 있음 
- workbook 기능은 현재 ocr_worker 중심의 비동기 파이프라인으로만 구현되어 있음 
- main.py에 workbook 라우터 연결 흔적은 있지만 활성화되어 있지는 않음 