import math
from collections import defaultdict

from app.common.exceptions.custom_exception import DependencyNotReadyException
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
        if req.raw_metrics.quests_clears_weekly < self.WARMUP_THRESHOLD:
            report = self._warmup_report(req)
        else:
            report = self._standard_report(req)

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
            if req.raw_metrics.quests_clears_weekly > 0
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


        # TODO: 추후 RAG + llm 도입하면 수정할 예정
        # summary_comment, analysis_text, metrics_analysis_comment, strategy_tip

        return ReportBody(
            report_mode="WARM_UP",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type="new_challenger",
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

    def _standard_report(self, req: ReportRequest) -> ReportBody:
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

        # TODO: RAG 조회 추가 + 424 에러 추가 + llm text 추가 예정


        # TODO : llm text로 변경 예정
        return ReportBody(
            report_mode="STANDARD",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type=self._user_type(growth_index),
                summary_comment=f"이번 주 핵심 보완 지표는 {weakest_metric}입니다.",
            ),
            past_diagnosis=PastDiagnosis(
                weak_section=weak_section,
                paragraph_fail_stats=req.paragraph_fail_stats,
                analysis_text=(
                    f"{weak_section} 문단에서 오답이 집중되었고,"
                    f"퀴즈 기준으로는 {weak_quiz} 축이 취약합니다."
                ),
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
                strategy_tip=(
                    f"{weak_section} 문단 우선 확인 + {weak_quiz} 유형 집중 훈련으로"
                    f"{weakest_metric} 지표를 먼저 개선하세요."
                ),
                recommended_action=self._recommended_action(weakest_metric),
            )
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

        clears = req.raw_metrics.quests_clears_weekly
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
        clears = max(req.raw_metrics.quests_clears_weekly, 1)
        sec_per_quest = req.raw_metrics.total_summary_complete_sec / clears

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
        clears = req.raw_metrics.quests_clears_weekly
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

    # TODO : 여기 이름 바꾸기
    def _user_type(self, growth_index: float) -> str:
        if growth_index >= 85:
            return "날카로운 매"
        if growth_index >= 70:
            return "steady_climber"
        if growth_index >= 55:
            return "growing_solver"
        return "new_challenger"

    # TODO: 여기 멘트 변경?
    def _metrics_comment(self, weakest_metric:str) -> str:
        mapping = {
            "accuracy": "제약사항 확인 후 풀이 시작 습관을 강화하세요.",
            "independence": "힌트 요청 전 15분 자가 시도 루틴을 적용하세요.",
            "efficiency": "목표 시간복잡도를 먼저 정하고 풀이를 선택하세요.",
            "consistency": "짧은 일일 학습 루틴으로 주간 연속성을 높이세요.",
        }
        return mapping.get(weakest_metric, "4대 지표의 균형을 유지하세요.")


    # TODO: llm text 기능 추가되면 삭제
    def _recommended_action(self, weakest_metric: str) -> str:
        mapping={
            "accuracy": "문제마다 CONSTRAINT를 먼저 표시하고 풀이를 시작하세요.",
            "independence": "한 문제당 힌트 없이 1회 완주 후 질문하세요.",
            "efficiency": "N 범위를 기준으로 O(...) 목표를 먼저 선언하세요.",
            "consistency": "하루 20분씩 주 5회 고정 학습 슬롯을 잡으세요.",
        }
        return mapping.get(weakest_metric, "취약 지표 중심으로 다음 주 계획을 세우세요.")

    def _clamp(self, value:float, lo:float, hi:float) -> float:
        return max(lo, min(hi, value))

report_service = ReportService()