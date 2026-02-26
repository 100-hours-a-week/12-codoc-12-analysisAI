from pydantic import BaseModel, Field

class AnalysisPeriod(BaseModel):
    start_date: str
    end_date: str

class ChatbotMessage(BaseModel):
    id: int
    user_id: int
    problem_id: int
    ai_message: str
    user_message: str
    node: str
    send_at: str

class RawMetrics(BaseModel):
    chatbot_msg_history: list[ChatbotMessage] = Field(default_factory=list)
    total_chatbot_requests: int = 0
    total_summary_complete_sec: int = 0
    quests_clears_weekly: int = 0

class ReportRequest(BaseModel):
    user_id: int
    user_level: str
    analysis_period: AnalysisPeriod
    raw_metrics: RawMetrics
    paragraph_fail_stats: dict[str, int] = Field(default_factory=dict)
    quiz_fail_stats: dict[str, int] = Field(default_factory=dict)

class ReportSummary(BaseModel):
    growth_index: float
    user_type: str
    summary_comment: str

class PastDiagnosis(BaseModel):
    weak_section: str
    paragraph_fail_stats: dict[str, int]
    analysis_text: str

class PresentGrowth(BaseModel):
    accuracy: float
    independence: float
    efficiency: float
    consistency: float
    metrics_analysis_comment: str
    is_imputed: bool = False

class FutureRoadmap(BaseModel):
    strategy_tip: str
    recommended_action: str

class ReportBody(BaseModel):
    report_mode: str
    summary: ReportSummary
    past_diagnosis: PastDiagnosis
    present_growth: PresentGrowth
    future_roadmap: FutureRoadmap

class ReportResponseData(BaseModel):
    user_id: int
    analysis_period: AnalysisPeriod
    report: ReportBody
