import math
import logging
from collections import defaultdict
from app.database.vector_db import vector_db
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

logger = logging.getLogger("codoc.report")

class ReportService:
    WARMUP_THRESHOLD = 2

    # TODO: LEVEL_BASE_LINE이랑 ROADMAP_BY_LEVEL => 이대로 할 것인지,,, 아니면 지표 바꿀 것인지 고민
    LEVEL_BASELINE = {
        "newbie": {"independence": 0.0, "consistency": 0.0, "efficiency": 0.0},
        "pupil": {"independence": 0.0, "consistency": 0.0, "efficiency": 0.0},
        "specialist": {"independence": 0.0, "consistency": 0.0, "efficiency": 0.0},
    }

    ROADMAP_BY_LEVEL = {
        "newbie": "풀이를 시작하기 전에 문제 목표와 제약 조건을 분리해 표시하고, 핵심 조건 2개를 체크리스트로 정리한 뒤 구현을 시작하세요.",
        "pupil": "풀이 시작 전 입력 규모와 제한 조건을 기준으로 처리 전략을 먼저 확정하고, 전략에 맞는 알고리즘을 선택해 진행하세요.",
        "specialist": "고난도 문제 2개를 선정해 알고리즘·자료구조 선택 근거와 검증 포인트를 각 1줄로 기록하고, 제출 전 반례 점검까지 수행하세요.",
    }


    async def generate_report(self, req: ReportRequest) -> ReportResponseData:
        if req.raw_metrics.solved_problems_weekly < self.WARMUP_THRESHOLD:
            report = self._warmup_report(req)
        else:
            report = await self._standard_report(req)

        await self._sync_report_metrics_to_user_memory(req, report)

        return ReportResponseData(
            user_id=req.user_id,
            analysis_period=req.analysis_period,
            report=report,
        )

    async def _sync_report_metrics_to_user_memory(
        self,
        req: ReportRequest,
        report: ReportBody,
    ) -> None:
        if req.problem_id is None:
            logger.info("event=report_memory_update_skip reason=missing_problem_id user_id=%s", req.user_id)
            return
        if not req.session_id:
            logger.info("event=report_memory_update_skip reason=missing_session_id user_id=%s problem_id=%s", req.user_id, req.problem_id)
            return
        if report.present_growth.is_imputed:
            logger.info(
                "event=report_memory_update_skip reason=imputed_scores user_id=%s problem_id=%s session_id=%s",
                req.user_id,
                req.problem_id,
                req.session_id,
            )
            return

        scores = {
            "accuracy_score": report.present_growth.accuracy,
            "independence_score": report.present_growth.independence,
            "speed_score": report.present_growth.efficiency,
            "consistency_score": report.present_growth.consistency,
        }

        try:
            updated = await vector_db.update_memory_scores(
                user_id=req.user_id,
                problem_id=req.problem_id,
                session_id=req.session_id,
                scores=scores,
            )
            if updated:
                logger.info(
                    "event=report_memory_update_success user_id=%s problem_id=%s session_id=%s",
                    req.user_id,
                    req.problem_id,
                    req.session_id,
                )
            else:
                logger.warning(
                    "event=report_memory_update_not_found user_id=%s problem_id=%s session_id=%s",
                    req.user_id,
                    req.problem_id,
                    req.session_id,
                )
        except Exception as e:
            logger.exception(
                "event=report_memory_update_error user_id=%s problem_id=%s session_id=%s error=%r",
                req.user_id,
                req.problem_id,
                req.session_id,
                e,
            )


    def _warmup_report(self, req: ReportRequest) -> ReportBody:
        # WARM_UP에서는 정밀 점수 대신 "분석 중" 상태를 보여주기 위해
        # 지표를 0.0으로 고정한다.
        accuracy = 0.0
        independence = 0.0
        efficiency = 0.0
        consistency = 0.0

        growth_index = self._growth_index(
            accuracy=accuracy,
            independence=independence,
            efficiency=efficiency,
            consistency=consistency,
        )

        weak_section = self._max_key(req.paragraph_fail_stats, default="UNKNOWN")


        return ReportBody(
            report_mode="WARM_UP",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type="잠재력 폭발 아기 코알라",
                summary_comment=(
                    "현재는 학습 데이터가 충분하지 않아 지표를 분석 중으로 표시하고 있어요. "
                    "이번 주 2문제를 달성하면 다음 리포트부터 개인 맞춤 정밀 분석으로 전환됩니다!"
                ),
            ),
            past_diagnosis=PastDiagnosis(
                weak_section=weak_section,
                paragraph_fail_stats=req.paragraph_fail_stats,
                analysis_text=(
                    "문제를 읽을 때 핵심 조건을 먼저 표시하는 습관을 만들면 "
                    "다음 리포트 정확도가 크게 올라갑니다."
                ),
            ),
            present_growth=PresentGrowth(
                accuracy=accuracy,
                independence=independence,
                efficiency=efficiency,
                consistency=consistency,
                metrics_analysis_comment=(
                    "현재 지표는 분석 중 상태로 제공됩니다. "
                    "학습 로그가 충분히 쌓이면 실제 기록 기반 점수로 자동 전환됩니다."
                ),
                is_imputed=True,
            ),
            future_roadmap=FutureRoadmap(
                strategy_tip=(
                    "문제마다 3단계로 진행해보세요. "
                    "1) GOAL/CONSTRAINT 밑줄 표시 "
                    "2) 예상 시간 복잡도 한 줄 메모 "
                    "3) 풀이 후 틀린 이유 1줄 기록"
                ),
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
            # 근거 문서가 비어도 424로 끊지 않고 STANDARD 폴백 리포트로 진행
            evidence_docs = []

        weakness_summary = {
            "weakest_metric": weakest_metric,
            "weak_section": weak_section,
            "weak_quiz": weak_quiz,
            "growth_index": growth_index,
            "present_growth": {
                "accuracy": accuracy,
                "independence": independence,
                "efficiency": efficiency,
                "consistency": consistency,
            },
        }

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
            paragraph_fail_stats=req.paragraph_fail_stats,
            quiz_fail_stats=req.quiz_fail_stats,
            weakness_summary=weakness_summary,
            evidence_docs=evidence_docs
        )

        return ReportBody(
            report_mode="STANDARD",
            summary=ReportSummary(
                growth_index=growth_index,
                user_type=self._user_type(growth_index),
                summary_comment=self._metrics_comment(weakest_metric),
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
                metrics_analysis_comment=llm_text["summary_comment"],
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

    def _metrics_comment(self, weakest_metric:str) -> str:
        mapping = {
            "accuracy": "유칼립투스 잎을 꼼꼼히 고르듯, 문제 속 제약사항을 한 번 더 살펴보면 실수가 줄어들 거예요🌿",
            "independence": "스스로 길을 찾는 코알라가 더 멀리 갈 수 있어요! 힌트를 보기 전 딱 5분만 더 고민해볼까요?",
            "efficiency": "속도라는 날개를 달아볼 시간! 문제를 읽을 때 목표와 제약조건을 먼저 표시하고 풀이 흐름을 한 줄로 정리한 뒤 시작하면 더 빠르게 접근할 수 있어요!",
            "consistency": "나무 위에서 매일 조금씩 쉬어가듯, 짧더라도 매일 학습하는 습관이 사용자의 가장 큰 무기가 될 거예요!",
        }
        return mapping.get(
            weakest_metric,
            "모든 지표가 골고루 성장하고 있어요! 이 균형을 유지하며서 한 단계 높은 문제로 성장 폭을 넓혀보세요!"
        )


    def _clamp(self, value:float, lo:float, hi:float) -> float:
        return max(lo, min(hi, value))

report_service = ReportService()
