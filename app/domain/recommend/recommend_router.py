from fastapi import APIRouter, HTTPException

from app.domain.recommend.recommendation_schemas import (
    FinalRecommendResponse,
    ProblemRecommendation,
    RecommendRequest,
    RecommendResponseData,
)

router = APIRouter()


@router.post("", response_model=FinalRecommendResponse)
async def get_recommendations(request: RecommendRequest):
    try:
        # TODO: 실제 서비스 로직(RecommendService) 호출 예정
        # 환경 세팅용 목업 데이터셋
        mock_recommendations = [
            ProblemRecommendation(
                problem_id=1,
                reason_msg="[환경세팅] 기본 추천 문제입니다. 조건문 해석 능력을 키우기 좋습니다.",
            ),
            ProblemRecommendation(
                problem_id=2,
                reason_msg="[환경세팅] 유저 수준에 맞는 연습 문제입니다.",
            ),
            ProblemRecommendation(
                problem_id=3,
                reason_msg="[환경세팅] 기본 추천 문제입니다. 조건문 해석 능력을 키우기 좋습니다.",
            ),
            ProblemRecommendation(
                problem_id=4,
                reason_msg="[환경세팅] 유저 수준에 맞는 연습 문제입니다.",
            ),
            ProblemRecommendation(
                problem_id=5,
                reason_msg="[환경세팅] 유저 수준에 맞는 연습 문제입니다.",
            ),
        ]

        response_data = RecommendResponseData(
            user_id=request.user_id,
            scenario=request.scenario,
            recommendations=mock_recommendations,
        )

        return FinalRecommendResponse(data=response_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
