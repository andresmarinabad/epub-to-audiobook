"""Routes for job management and progress streaming."""
from __future__ import annotations

import json
import os
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ..auth import require_api_key
from ..deps import get_epub_reader, get_job_store, get_progress_bus
from ..schemas import ChapterState, JobStatusResponse, StartJobRequest, StartJobResponse
from ....application.services import ParseEpubService
from ....domain.models import ConversionOptions, Job, JobStatus
from ....infrastructure.celery.tasks import dispatch_conversion

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Start a conversion job
# ---------------------------------------------------------------------------

@router.post("", response_model=StartJobResponse, dependencies=[Depends(require_api_key)])
async def start_job(body: StartJobRequest) -> StartJobResponse:
    reader = get_epub_reader()
    service = ParseEpubService(reader)

    chapters, title, author = service.parse_txt(body.txt_content)
    if not chapters:
        raise HTTPException(status_code=422, detail="No chapters found in the provided text")

    options = ConversionOptions(
        voice=body.voice,
        sentence_pause_ms=body.sentence_pause_ms,
        paragraph_pause_ms=body.paragraph_pause_ms,
        chapter_pause_ms=body.chapter_pause_ms,
    )

    job = Job.create(
        book_title=title,
        book_author=author,
        chapters=chapters,
        voice=body.voice,
    )

    store = get_job_store()
    store.save(job)

    # Build chapter dicts with paragraphs (domain Chapter objects have them)
    chapters_with_paragraphs = [
        {"index": c.index, "title": c.title, "paragraphs": c.paragraphs}
        for c in chapters
    ]

    dispatch_conversion(job, chapters_with_paragraphs, options, cover_path=body.cover_path)

    return StartJobResponse(
        job_id=job.id,
        total_chapters=job.total_chapters,
        book_title=job.book_title,
        book_author=job.book_author,
    )


# ---------------------------------------------------------------------------
# Get job status (polling fallback)
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobStatusResponse, dependencies=[Depends(require_api_key)])
async def get_job(job_id: str) -> JobStatusResponse:
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


# ---------------------------------------------------------------------------
# SSE progress stream
# ---------------------------------------------------------------------------

@router.get("/{job_id}/stream", dependencies=[Depends(require_api_key)])
async def stream_progress(job_id: str) -> StreamingResponse:
    store = get_job_store()
    bus = get_progress_bus()

    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _generate() -> AsyncIterator[str]:
        # Send current state immediately
        current = store.get(job_id)
        if current:
            yield _sse(_to_response(current).model_dump())

        # If already finished, just send the final event and close
        if current and current.status in (JobStatus.DONE, JobStatus.ERROR):
            yield _sse({"status": current.status.value})
            return

        # Stream live updates — only terminate on a JOB-level done/error event,
        # not on a chapter-level "done" (which has the same status string value).
        _terminal = {JobStatus.DONE.value, JobStatus.ERROR.value}
        async for event in bus.subscribe(job_id):
            refreshed = store.get(job_id)
            if refreshed:
                yield _sse(_to_response(refreshed).model_dump())

            if event.get("type") == "job" and event.get("status") in _terminal:
                break

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Download finished M4B
# ---------------------------------------------------------------------------

@router.get("/{job_id}/download", dependencies=[Depends(require_api_key)])
async def download_m4b(job_id: str) -> FileResponse:
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.m4b_path:
        raise HTTPException(status_code=409, detail="Audiobook is not ready yet")
    if not os.path.exists(job.m4b_path):
        raise HTTPException(status_code=410, detail="File has expired or was removed")

    filename = os.path.basename(job.m4b_path)
    return FileResponse(
        path=job.m4b_path,
        media_type="audio/mp4",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        overall_progress=job.overall_progress,
        book_title=job.book_title,
        book_author=job.book_author,
        voice=job.voice,
        total_chapters=job.total_chapters,
        chapters=[
            ChapterState(
                index=c.index,
                title=c.title,
                status=c.status.value,
                progress=c.progress,
                error=c.error,
            )
            for c in job.chapters
        ],
        error=job.error,
        m4b_ready=job.status == JobStatus.DONE and job.m4b_path is not None,
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
