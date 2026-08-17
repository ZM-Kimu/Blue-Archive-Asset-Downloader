from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from ba_downloader.api.jobs import TERMINAL_STATUSES
from ba_downloader.api.services import ApiServices


async def job_event_stream(services: ApiServices, job_id: str) -> AsyncIterator[str]:
    if services.shutdown_event.is_set():
        return
    job = services.jobs.get(job_id)
    cursor = job.next_event_id - 1
    yield sse(cursor, "snapshot", {"job": services.job_view(job)})
    heartbeat_deadline = asyncio.get_running_loop().time() + 15.0
    while not services.shutdown_event.is_set():
        events = services.jobs.events_after(job_id, cursor)
        for event in events:
            cursor = event.id
            yield sse(event.id, event.type, event.as_dict())
        job = services.jobs.get(job_id)
        if job.status in TERMINAL_STATUSES and not events:
            return
        now = asyncio.get_running_loop().time()
        if now >= heartbeat_deadline:
            yield ": heartbeat\n\n"
            heartbeat_deadline = now + 15.0
        await asyncio.sleep(0.25)


def sse(event_id: int, event_type: str, payload: object) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=True, default=str)}\n\n"
    )
