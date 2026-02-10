from typing import List, Optional
from pydantic import BaseModel, Field

class RecommendFilterInfo(BaseModel):
    solved_problem_ids: List[int] = Field(..., description="푼 문제 ID")
    challenge_problem_ids: List[int] = Field(..., description="현재 도전 중인 문제 ID")

class RecommendRequest(BaseModel):
    user_id : int
    user_level : str = Field(..., pattern="^(newbie|pupil|specialist)$")
    scenario: str = Field(..., pattern="^(DAILY|ON_DEMAND)$")
    filter_info: RecommendFilterInfo

class ProblemRecommendation(BaseModel):
    problem_id: int
    reason_msg: str

class RecommendResponseData(BaseModel):
    user_id : int
    scenario : str
    recommendations : List[ProblemRecommendation]

class FinalRecommendResponse(BaseModel):
    code : int = 200
    message : str = "OK"
    data : RecommendResponseData

