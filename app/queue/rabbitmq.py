from typing import Optional

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection

from app.core.config import settings
from app.queue.constants import ALL_QUEUE_NAMES

_connection: Optional[AbstractRobustConnection] = None
_channel: Optional[AbstractRobustChannel] = None

async def init_rabbitmq() -> None:
    global _connection, _channel

    _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    _channel = await _connection.channel()

    # worker가 붙을 때 과도한 동시 처리 방지용
    await _channel.set_qos(prefetch_count=10)

    for queue_name in ALL_QUEUE_NAMES:
        await _channel.declare_queue(queue_name, durable=True)

async def close_rabbitmq() -> None:
    global _connection, _channel

    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()

    _channel = None
    _connection = None

def get_rabbitmq_channel() -> AbstractRobustChannel:
    if _channel is None:
        raise RuntimeError("RabbitMQ channel is not initialized. Call init_rabbitmq() first.")
    return _channel