import asyncio
import contextlib
import json
import signal
from collections.abc import Callable
from typing import Any, Awaitable
from datetime import datetime, timezone

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage
from pydantic import BaseModel

from app.common.exceptions.base_exception import BusinessException
from app.domain.recommend.recommend_usecase import generate_recommendations_usecase
from app.domain.report.report_service import report_service
from app.domain.recommend.recommendation_schemas import RecommendRequest
from app.domain.report.report_schemas import ReportRequest
from app.queue.constants import RECOMMEND_REQUEST_QUEUE, REPORT_REQUEST_QUEUE, RECOMMEND_RESPONSE_QUEUE, REPORT_RESPONSE_QUEUE
from app.queue.rabbitmq import close_rabbitmq, get_rabbitmq_channel, init_rabbitmq

# 타임아웃 처리
AI_PROCESS_TIMEOUT_SEC = 90
AI_PROCESS_MAX_RETRIES = 1
RETRY_BACKOFF_SEC = 1.0

class WorkerRequestEnvelope(BaseModel):
    job_id: str
    requested_at: str
    payload: dict[str, Any]

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _validate(model_cls, data):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)

def _to_dict(value: Any) -> dict[str, Any] | Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value

def _extract_error(e: Exception) -> tuple[str, str]:
    if isinstance(e, BusinessException):
        return e.errorCode, e.message
    if isinstance(e, asyncio.TimeoutError):
        return "AI_TIMEOUT", f"AI processing timed out ({AI_PROCESS_TIMEOUT_SEC}s)"
    return "INTERNAL_ERROR", str(e)

def _parse_envelope(message: AbstractIncomingMessage) -> WorkerRequestEnvelope:
    raw = message.body.decode("utf-8")
    obj = json.loads(raw)
    return _validate(WorkerRequestEnvelope, obj)


def _parse_recommend_request(
        message: AbstractIncomingMessage,
) -> tuple[str, str, RecommendRequest]:
    env = _parse_envelope(message)
    req = _validate(RecommendRequest, env.payload)
    return env.job_id, env.requested_at, req


def _parse_report_request(
        message: AbstractIncomingMessage,
) -> tuple[str, str, ReportRequest]:
    env = _parse_envelope(message)
    req = _validate(ReportRequest, env.payload)
    return env.job_id, env.requested_at, req

def _try_extract_job_id(message: AbstractIncomingMessage) -> str | None:
    try:
        raw = message.body.decode("utf-8")
        obj= json.loads(raw)
        job_id = obj.get("job_id")
        return str(job_id) if job_id else None
    except Exception:
        return None

async def _publish_json(queue_name: str, payload: dict[str, Any]) -> None:
    channel = get_rabbitmq_channel()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await channel.default_exchange.publish(
        Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        ),
        routing_key=queue_name,
    )

async def _run_with_timeout_and_retry(
        coro_factory: Callable[..., Awaitable[Any]], *args: Any
) -> Any:
    total_attempts = AI_PROCESS_MAX_RETRIES + 1
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            return await asyncio.wait_for(
                coro_factory(*args),
                timeout= AI_PROCESS_TIMEOUT_SEC,
            )
        except BusinessException:
            raise
        except Exception as e:
            last_error = e
            if attempt < total_attempts:
                print(f"[retry] attempt = {attempt}/{total_attempts} error={type(e).__name__}")
                await asyncio.sleep(RETRY_BACKOFF_SEC * attempt)
                continue
            break

    assert last_error is not None
    raise last_error

async def _handle_parse_failure(
        message: AbstractIncomingMessage,
        response_queue: str,
        parse_error: Exception,
) -> None:
    job_id = _try_extract_job_id(message)

    if not job_id:
        print(f"[parse-fail] no job_id, reject requeue=False error={parse_error!r}")
        await message.reject(requeue=False)
        return

    failed_payload = {
        "job_id": job_id,
        "status": "FAILED",
        "responded_at": _utc_now_iso(),
        "error_code": "INVALID_REQUEST_SCHEMA",
        "error_message": str(parse_error),
    }

    try:
        await _publish_json(response_queue, failed_payload)
        await message.ack()
        print(f"[parse-fail] failed-response published job_id={job_id}")
    except Exception as publish_error:
        print(f"[parse-fail] publish-fail job_id={job_id} error={publish_error!r}, requeue=True")
        await message.nack(requeue=True)


async def handle_recommend(message: AbstractIncomingMessage) -> None:
    try:
        job_id, requested_at, req = _parse_recommend_request(message)
    except Exception as parse_error:
        await _handle_parse_failure(message, RECOMMEND_RESPONSE_QUEUE, parse_error)
        return

    try:
        print(f"[recommend] start job_id={job_id} requested_at={requested_at} user_id={req.user_id}")
        recommend_data = await _run_with_timeout_and_retry(
            generate_recommendations_usecase, req
        )

        success_payload = {
            "job_id": job_id,
            "status": "SUCCESS",
            "responded_at": _utc_now_iso(),
            "result": _to_dict(recommend_data),
        }
        await _publish_json(RECOMMEND_RESPONSE_QUEUE, success_payload)
        await message.ack()
        print(f"[recommend] success job_id={job_id}")
    except Exception as e:
        error_code, error_message = _extract_error(e)
        failed_payload = {
            "job_id": job_id,
            "status": "FAILED",
            "responded_at": _utc_now_iso(),
            "error_code": error_code,
            "error_message": error_message,
        }
        try:
            await _publish_json(RECOMMEND_RESPONSE_QUEUE, failed_payload)
            await message.ack()
            print(f"[recommend] failed job_id={job_id} code={error_code}")
        except Exception as publish_error:
            print(f"[recommend] publish-fail job_id={job_id} error={publish_error!r}, requeue=True")
            await message.nack(requeue=True)

async def handle_report(message: AbstractIncomingMessage) -> None:
    try:
        job_id, requested_at, req = _parse_report_request(message)
    except Exception as parse_error:
        await _handle_parse_failure(message, REPORT_RESPONSE_QUEUE, parse_error)
        return

    try:
        print(f"[report] start job_id={job_id} requested_at={requested_at} user_id={req.user_id}")
        report_data = await _run_with_timeout_and_retry(
            report_service.generate_report, req
        )

        success_payload = {
            "job_id": job_id,
            "status": "SUCCESS",
            "responded_at": _utc_now_iso(),
            "result": _to_dict(report_data),
        }
        await _publish_json(REPORT_RESPONSE_QUEUE, success_payload)
        await message.ack()
        print(f"[report] success job_id={job_id}")
    except Exception as e:
        error_code, error_message = _extract_error(e)
        failed_payload = {
            "job_id": job_id,
            "status": "FAILED",
            "responded_at": _utc_now_iso(),
            "error_code": error_code,
            "error_message": error_message,
        }
        try:
            await _publish_json(REPORT_RESPONSE_QUEUE, failed_payload)
            await message.ack()
            print(f"[report] failed job_id={job_id} code={error_code}")
        except Exception as publish_error:
            print(f"[report] publish-fail job_id={job_id} error={publish_error!r}, requeue=True")
            await message.nack(requeue=True)

async def consume_recommend() -> None:
    channel = get_rabbitmq_channel()
    queue = await channel.declare_queue(RECOMMEND_REQUEST_QUEUE, durable=True)
    await queue.consume(handle_recommend)
    print(f"[*] consuming: {RECOMMEND_REQUEST_QUEUE}")

async def consume_report() -> None:
    channel = get_rabbitmq_channel()
    queue = await channel.declare_queue(REPORT_REQUEST_QUEUE, durable=True)
    await queue.consume(handle_report)
    print(f"[*] consuming: {REPORT_REQUEST_QUEUE}")

async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    await init_rabbitmq()
    try:
        await consume_report()
        await consume_recommend()
        print("[*] AI worker started")
        await stop_event.wait()
    finally:
        await close_rabbitmq()
        print("[*] AI worker stopped")

if __name__ == "__main__":
    asyncio.run(main())