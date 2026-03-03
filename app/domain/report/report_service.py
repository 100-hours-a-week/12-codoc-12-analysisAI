import math
from collections import defaultdict

from app.common.exceptions.custom_exception import DependencyNotReadyException
from app.domain.report.report_llm_service import report_llm_service
from app.domain.report.report_rag_service import report_rag_service
from app.domain.report.report_schemas import (
    FutureRoadmap,
    PastDiagnosis,
    PresentGrowth,
    ReportBody,
    ReportRequest,
    ReportResponseData,
    ReportSummary,
)

class ReportService:
    WARMUP_THRESHOLD = 3

    # TODO: LEVEL_BASE_LINE이랑 ROADMAP_BY_LEVEL => 이대로 할 것인지,,, 아니면 지표 바꿀 것인지 고민
    LEVEL_BASELINE = {
        "newbie": {"independence": 65.0, "consistency": 50.0, "efficiency": 65.0},
        "pupil": {"independence": 72.0, "consistency": 60.0, "efficiency": 72.0},
        "specialist": {"independence": 80.0, "consistency": 70.0, "efficiency": 78.0},
    }

    ROADMAP_BY_LEVEL = {
        "newbie": "이번 주는 문제를 풀기 전에 GOAL/CONSTRAINT에 밑줄을 치고, 조건 2개 이상을 먼저 메모해보세요.",
        "pupil": "풀이 시작 전에 N 범위와 목표 시간복잡도(O(...))를 먼저 정한 뒤, 그에 맞는 풀이를 고르세요.",
        "specialist": "고난도 문제 2개를 골라 자료구조 선택 근거와 복잡도 근거를 한 줄씩 남기며 풀어보세요.",
    }


    async def generate_report(self, req: ReportRequest) -> ReportResponseData:
        if req.raw_metrics.solved_problems_weekly < self.WARMUP_THRESHOLD:
            report = self._warmup_report(req)
        else:
            report = await self._standard_report(req)

        return ReportResponseData(
            user_id=req.user_id,
            analysis_period=req.analysis_period,
            report=report,
        )


    def _warmup_report(self, req: ReportRequest) -> ReportBody:
        base = self.LEVEL_BASELINE.get(req.user_level, self.LEVEL_BASELINE["newbie"])

        accuracy = self._calculate_accuracy(req)
        independence = base["independence"]
        efficiency = (
            self._calculate_efficiency(req)
            if req.raw_metrics.solved_problems_weekly  > 0
            else base["efficiency"]
        )
        consistency = base["consistency"]

        growth_index = self._growth_index(
            accuracy=accuracy,
            independence=independence,
            efficiency=efficiency,
            consistency=consistency,
        )

        weak_section = self._max_key(req.paragraph_fail_stats, default="UNKNOWN")

        # TODO : 수정 예정
        return ReportBody(
            report_mode="WARM_UP",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type="잠재력 폭발 아기 코알라",
                summary_comment="좋은 출발이에요. 아직 데이터가 적어 이번 주는 가벼운 온보딩 리포트로 안내드릴게요!",
            ),
            past_diagnosis=PastDiagnosis(
                weak_section=weak_section,
                paragraph_fail_stats=req.paragraph_fail_stats,
                analysis_text="학습 데이터가 충분하지 않아 정밀 진단 대신 온보딩 진단을 제공합니다.",
            ),
            present_growth=PresentGrowth(
                accuracy=accuracy,
                independence=independence,
                efficiency=efficiency,
                consistency=consistency,
                metrics_analysis_comment="독립성/일관성은 현재 레벨 평균치로 대체되었습니다.",
                is_imputed=True,
            ),
            future_roadmap=FutureRoadmap(
                strategy_tip="이번 주 2~3문제만 더 풀면 개인화 정밀 분석으로 전환됩니다.",
                recommended_action=self.ROADMAP_BY_LEVEL.get(
                    req.user_level, self.ROADMAP_BY_LEVEL["newbie"]
                )
            ),
        )

    async def _standard_report(self, req: ReportRequest) -> ReportBody:
        accuracy = self._calculate_accuracy(req)
        independence = self._calculate_independence(req)
        efficiency = self._calculate_efficiency(req)
        consistency = self._calculate_consistency(req)

        growth_index = self._growth_index(
            accuracy=accuracy,
            independence=independence,
            efficiency=efficiency,
            consistency=consistency,
        )

        weak_section = self._max_key(req.paragraph_fail_stats, default="UNKNOWN")
        weak_quiz = self._max_key(req.quiz_fail_stats, default="UNKNOWN")
        weakest_metric = self._weakest_metric(
            accuracy=accuracy,
            independence=independence,
            efficiency=efficiency,
            consistency=consistency,
        )

        evidence_docs = await report_rag_service.retrieve_evidence(
            weak_section=weak_section,
            weak_quiz=weak_quiz,
            weakest_metric=weakest_metric,
            user_level=req.user_level,
            top_k=3
        )

        if not evidence_docs:
            raise DependencyNotReadyException()

        llm_text = await report_llm_service.generate_sections(
            user_level=req.user_level,
            report_mode="STANDARD",
            growth_index=growth_index,
            weak_section=weak_section,
            weak_quiz=weak_quiz,
            weakest_metric=weakest_metric,
            present_growth={
                "accuracy": accuracy,
                "independence": independence,
                "efficiency": efficiency,
                "consistency": consistency,
            },
            evidence_docs=evidence_docs
        )

        return ReportBody(
            report_mode="STANDARD",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type=self._user_type(growth_index),
                summary_comment=llm_text["summary_comment"],
            ),
            past_diagnosis=PastDiagnosis(
                weak_section=weak_section,
                paragraph_fail_stats=req.paragraph_fail_stats,
                analysis_text=llm_text["analysis_text"],
            ),
            present_growth=PresentGrowth(
                accuracy=accuracy,
                independence=independence,
                efficiency=efficiency,
                consistency=consistency,
                metrics_analysis_comment=self._metrics_comment(weakest_metric),
                is_imputed=False,
            ),
            future_roadmap=FutureRoadmap(
                strategy_tip=llm_text["strategy_tip"],
                recommended_action=llm_text["recommended_action"],
            ),
        )


    # -- 계산 로직 --
    def _calculate_accuracy(self, req:ReportRequest) -> float:
        history = req.raw_metrics.chatbot_msg_history

        if history:
            first_by_node = self._extract_first_message_by_node(history)
            if not first_by_node:
                return 60.0

            quality_sum = 0.0
            for msg in first_by_node.values():
                length = len((msg or "").strip())
                if length >= 20:
                    quality_sum += 1.0
                elif length >= 8:
                    quality_sum += 0.75
                elif length > 0:
                    quality_sum += 0.5

            ratio = quality_sum / len(first_by_node)
            return round(self._clamp(60 + ratio * 40, 0, 100),1)

        clears = req.raw_metrics.solved_problems_weekly
        fails = sum(req.paragraph_fail_stats.values())
        denom = clears + fails

        if denom <= 0:
            return 60.0
        return round((clears/denom) * 100, 1)


    def _calculate_independence(self, req:ReportRequest) -> float:
        history = req.raw_metrics.chatbot_msg_history
        if not history:
            return 100.0

        hint_keywords = ["힌트", "모르겠", "help", "i don't know", "모르겠어요"]
        hint_count = 0
        loop_count_by_problem = defaultdict(int)

        for h in history:
            text = (h.user_message or "").lower()
            if any(k in text for k in hint_keywords):
                hint_count += 1
            loop_count_by_problem[h.problem_id] += 1

        avg_loop = (
            sum(loop_count_by_problem.values()) / len(loop_count_by_problem)
            if loop_count_by_problem
            else 0.0
        )

        penalty = math.log1p(hint_count) * 18 + math.log1p(avg_loop) * 10
        return round(self._clamp(100 - penalty, 0, 100), 1)

    def _calculate_efficiency(self, req:ReportRequest) -> float:
        clears = max(req.raw_metrics.solved_problems_weekly , 1)
        sec_per_quest = req.raw_metrics.solve_duration_sec / clears

        if sec_per_quest <= 300:
            return 95.0
        if sec_per_quest <= 600:
            return 85.0
        if sec_per_quest <= 900:
            return 75.0
        if sec_per_quest <= 1200:
            return 65.0
        return 50.0


    def _calculate_consistency(self, req: ReportRequest) -> float:
        clears = req.raw_metrics.solved_problems_weekly
        return round(self._clamp((clears/14) * 100, 0, 100),1)

    def _growth_index(self, *, accuracy:float, independence:float, efficiency:float, consistency:float) -> float:
        score = (
            accuracy * 0.4
            + independence * 0.3
            + efficiency * 0.2
            + consistency * 0.1
        )
        return round(score, 1)

    # -- 유틸 --
    def _extract_first_message_by_node(self, history: list) -> dict[str, str]:
        first = {}
        for item in history:
            prev = first.get(item.node)
            if prev is None or item.send_at < prev ["send_at"]:
                first[item.node] = {"send_at": item.send_at, "msg": item.user_message}
        return {k: v["msg"] for k,v in first.items()}


    def _max_key(self, data: dict[str, int], default: str) -> str:
        if not data:
            return default
        return max(data, key=data.get)

    def _weakest_metric(self, *, accuracy:float, independence:float, efficiency:float, consistency:float) -> str:
        metrics = {
            "accuracy": accuracy,
            "independence": independence,
            "efficiency": efficiency,
            "consistency": consistency,
        }
        return min(metrics, key=metrics.get)

    def _user_type(self, growth_index: float) -> str:
        if growth_index >= 85:
            return "숲을 지배한 코알라"
        if growth_index >= 70:
            return "뿌리 깊은 코알라"
        if growth_index >= 55:
            return "번개 맞은 코알라"
        return "잠재력 폭발 아기 코알라"

    # TODO: 여기 멘트 변경
    def _metrics_comment(self, weakest_metric:str) -> str:
        mapping = {
            "accuracy": "유칼립투스 잎을 꼼꼼히 고르듯, 문제 속 제약사항(CONSTRAINT)을 한 번 더 살펴보면 실수가 줄어들 거예요.",
            "independence": "스스로 길을 찾는 코알라가 더 멀리 갈 수 있어요. 힌트를 보기 전 딱 5분만 더 고민해볼까요?",
            "efficiency": "속도라는 날개를 달아볼 시간! 코드를 짜기 전, 이 문제에 가장 어울리는 시간복잡도가 무엇일지 먼저 그려보세요.",
            "consistency": "나무 위에서 매일 조금씩 쉬어가듯, 짧더라도 매일 학습하는 습관이 예진님의 가장 큰 무기가 될 거예요.",
        }
        return mapping.get(
            weakest_metric,
            "모든 지표가 골고루 성장하고 있어요! 이 균형을 유지하며 다음 단계로 나아가봐요."
        )

    # 좀 더 전문적인 버전,,
    # def _metrics_comment(self, weakest_metric:str) -> str:
    #     mapping = {
    #         "accuracy": "문제의 요구사항을 로직으로 전환하는 과정에서 미세한 누수가 발생하고 있습니다. 제약 조건(Constraint)의 엄격한 준수가 필요합니다.",
    #         "independence": "문제 해결 과정에서 외부 의존성이 높게 측정되었습니다. 스스로 로직을 설계하고 검증하는 완결성 강화가 시급합니다.",
    #         "efficiency": "구현의 정확성에 비해 자원 활용 효율이 아쉽습니다. 알고리즘 선택 전, 데이터 규모에 따른 최적 복잡도를 산정하는 습관이 필요합니다.",
    #         "consistency": "학습 데이터의 밀도가 불규칙합니다. 실력의 정체기를 돌파하기 위해서는 일정한 리듬의 규칙적인 훈련 로그가 뒷받침되어야 합니다.",
    #     }
    # return mapping.get(weakest_metric, "전반적인 지표가 균형 있게 성장 중입니다. 현재의 학습 템포를 유지하며 난이도를 점진적으로 높여보세요.")


    def _clamp(self, value:float, lo:float, hi:float) -> float:
        return max(lo, min(hi, value))

report_service = ReportService()
