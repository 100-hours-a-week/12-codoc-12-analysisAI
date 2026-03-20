import asyncio
import contextlib
import json
import signal
from typing import Any
from datetime import datetime, timezone

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage

from app.common.exceptions.base_exception import BusinessException
from app.domain.workbook.workbook_service import workbook_service
from app.domain.workbook.workbook_llm_service import workbook_llm_service
from app.domain.workbook.workbook_schemas import WorkbookQueueRequest, WorkbookResponseData
from app.queue.constants import OCR_REQUEST_QUEUE, OCR_EXCHANGE, OCR_RESPONSE_ROUTING_KEY
from app.queue.rabbitmq import get_rabbitmq_channel, init_rabbitmq, close_rabbitmq

OCR_PROCESS_TIMEOUT_SEC = 300


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _try_extract_custom_problem_id(message: AbstractIncomingMessage) -> int | None:
    try:
        obj = json.loads(message.body.decode("utf-8"))
        cid = obj.get("customProblemId")
        return int(cid) if cid is not None else None
    except Exception:
        return None


def _to_dict(value: Any) -> dict[str, Any] | Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


async def _publish_response(custom_problem_id: int, payload: dict[str, Any]) -> None:
    channel = get_rabbitmq_channel()
    exchange = await channel.get_exchange(OCR_EXCHANGE)
    body = json.dumps({"customProblemId": custom_problem_id, "response": payload}, ensure_ascii=False).encode("utf-8")
    await exchange.publish(
        Message(body=body, content_type="application/json", delivery_mode=DeliveryMode.PERSISTENT),
        routing_key=OCR_RESPONSE_ROUTING_KEY,
    )


async def _run_pipeline(req: WorkbookQueueRequest) -> WorkbookResponseData:
    problem_detail = await workbook_service.extract_problem(req)
    summary_cards, quizzes = await workbook_llm_service.generate(problem_detail)
    return WorkbookResponseData(
        problem_detail=problem_detail,
        summary_card=summary_cards,
        quiz=quizzes,
    )


async def handle_ocr(message: AbstractIncomingMessage) -> None:
    custom_problem_id = _try_extract_custom_problem_id(message)

    try:
        obj = json.loads(message.body.decode("utf-8"))
        req = WorkbookQueueRequest.model_validate(obj)
        custom_problem_id = req.customProblemId
    except Exception as parse_error:
        if custom_problem_id is None:
            print(f"[ocr] parse failed, no customProblemId, reject: {parse_error!r}")
            await message.reject(requeue=False)
            return
        failed = {"code": "FAILED", "message": f"요청 형식이 올바르지 않습니다: {parse_error}", "data": None}
        try:
            await _publish_response(custom_problem_id, failed)
            await message.ack()
        except Exception as pub_err:
            print(f"[ocr] publish-fail id={custom_problem_id} err={pub_err!r}")
            await message.nack(requeue=True)
        return

    try:
        print(f"[ocr] start customProblemId={custom_problem_id}")
        result = await asyncio.wait_for(_run_pipeline(req), timeout=OCR_PROCESS_TIMEOUT_SEC)

        success = {
            "code": "SUCCESS",
            "message": "문제 분석이 완료되었습니다.",
            "data": _to_dict(result),
        }
        await _publish_response(custom_problem_id, success)
        await message.ack()
        print(f"[ocr] success customProblemId={custom_problem_id}")

    except Exception as e:
        if isinstance(e, BusinessException):
            error_code, error_message = e.errorCode, e.message
        elif isinstance(e, asyncio.TimeoutError):
            error_code, error_message = "AI_TIMEOUT", f"처리 시간이 초과되었습니다 ({OCR_PROCESS_TIMEOUT_SEC}s)"
        else:
            error_code, error_message = "INTERNAL_ERROR", str(e)

        print(f"[ocr] failed customProblemId={custom_problem_id} code={error_code} message={error_message}")
        failed = {"code": error_code, "message": error_message, "data": None}
        try:
            await _publish_response(custom_problem_id, failed)
            await message.ack()
        except Exception as pub_err:
            print(f"[ocr] publish-fail id={custom_problem_id} err={pub_err!r}")
            await message.nack(requeue=True)


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    await init_rabbitmq()
    try:
        channel = get_rabbitmq_channel()
        await channel.set_qos(prefetch_count=5)
        queue = await channel.declare_queue(OCR_REQUEST_QUEUE, durable=True)
        await queue.consume(handle_ocr)
        print(f"[*] OCR worker started, consuming: {OCR_REQUEST_QUEUE}")
        await stop_event.wait()
    finally:
        await close_rabbitmq()
        print("[*] OCR worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
