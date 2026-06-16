"""
Adapters: IJobStore (sync, for Celery workers) + IProgressBus (async, for FastAPI SSE).
Both backed by Redis.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import redis
import redis.asyncio as aioredis

from ...domain.models import (
    Chapter,
    ChapterStatus,
    Job,
    JobStatus,
)
from ...domain.ports import IJobStore, IProgressBus

_JOB_TTL = 86_400  # 24 hours


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "book_title": job.book_title,
        "book_author": job.book_author,
        "voice": job.voice,
        "status": job.status.value,
        "total_chapters": job.total_chapters,
        "overall_progress": job.overall_progress,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "m4b_path": job.m4b_path,
        "error": job.error,
        "chapters": [_chapter_to_dict(c) for c in job.chapters],
    }


def _chapter_to_dict(c: Chapter) -> dict:
    return {
        "index": c.index,
        "title": c.title,
        "status": c.status.value,
        "progress": c.progress,
        "file_path": c.file_path,
        "error": c.error,
    }


def _dict_to_job(d: dict) -> Job:
    chapters = [
        Chapter(
            index=ch["index"],
            title=ch["title"],
            paragraphs=[],  # not stored in Redis — only needed during conversion
            status=ChapterStatus(ch["status"]),
            progress=ch["progress"],
            file_path=ch.get("file_path"),
            error=ch.get("error"),
        )
        for ch in d.get("chapters", [])
    ]
    return Job(
        id=d["id"],
        book_title=d["book_title"],
        book_author=d["book_author"],
        voice=d["voice"],
        status=JobStatus(d["status"]),
        chapters=chapters,
        created_at=datetime.fromisoformat(d["created_at"]),
        finished_at=datetime.fromisoformat(d["finished_at"]) if d.get("finished_at") else None,
        m4b_path=d.get("m4b_path"),
        error=d.get("error"),
    )


# ---------------------------------------------------------------------------
# Sync store  (used by Celery workers)
# ---------------------------------------------------------------------------

class RedisJobStore(IJobStore):
    def __init__(self, redis_url: str) -> None:
        self._r = redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def save(self, job: Job) -> None:
        self._r.setex(self._key(job.id), _JOB_TTL, json.dumps(_job_to_dict(job)))

    def get(self, job_id: str) -> Optional[Job]:
        raw = self._r.get(self._key(job_id))
        return _dict_to_job(json.loads(raw)) if raw else None

    def update_chapter(
        self,
        job_id: str,
        chapter_index: int,
        status: ChapterStatus,
        progress: float,
        file_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        key = self._key(job_id)
        raw = self._r.get(key)
        if not raw:
            return
        data = json.loads(raw)
        for ch in data["chapters"]:
            if ch["index"] == chapter_index:
                ch["status"] = status.value
                ch["progress"] = progress
                if file_path is not None:
                    ch["file_path"] = file_path
                if error is not None:
                    ch["error"] = error
                break
        # Recompute overall progress
        data["overall_progress"] = (
            sum(c["progress"] for c in data["chapters"]) / len(data["chapters"])
            if data["chapters"] else 0.0
        )
        self._r.setex(key, _JOB_TTL, json.dumps(data))
        # Publish to the progress channel so SSE picks it up
        self._r.publish(
            f"job:{job_id}:updates",
            json.dumps({
                "type": "chapter",
                "chapter_index": chapter_index,
                "status": status.value,
                "progress": progress,
                "overall_progress": data["overall_progress"],
            }),
        )

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        m4b_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        key = self._key(job_id)
        raw = self._r.get(key)
        if not raw:
            return
        data = json.loads(raw)
        data["status"] = status.value
        if m4b_path is not None:
            data["m4b_path"] = m4b_path
        if error is not None:
            data["error"] = error
        if status in (JobStatus.DONE, JobStatus.ERROR):
            data["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._r.setex(key, _JOB_TTL, json.dumps(data))
        self._r.publish(
            f"job:{job_id}:updates",
            json.dumps({"type": "job", "status": status.value, "error": error}),
        )


# ---------------------------------------------------------------------------
# Async progress bus  (used by FastAPI SSE endpoint)
# ---------------------------------------------------------------------------

class RedisProgressBus(IProgressBus):
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url

    async def publish(self, job_id: str, payload: dict) -> None:
        async with aioredis.from_url(self._url, decode_responses=True) as r:
            await r.publish(f"job:{job_id}:updates", json.dumps(payload))

    async def subscribe(self, job_id: str) -> AsyncIterator[dict]:  # type: ignore[override]
        async with aioredis.from_url(self._url, decode_responses=True) as r:
            pubsub = r.pubsub()
            await pubsub.subscribe(f"job:{job_id}:updates")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
