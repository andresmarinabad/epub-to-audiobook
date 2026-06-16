"""
Celery tasks — thin orchestration layer that wires adapters to application services.

Parallelism model:
  • One Celery task per chapter (convert_chapter).
  • Worker concurrency = max(1, nproc-2) → set in entrypoint-worker.sh.
  • All convert_chapter tasks run inside a Celery `group` → parallel.
  • After all complete, merge_audiobook is called via a `chord` callback.
  • Within each chapter, edge-tts sentences are synthesized concurrently
    (asyncio + semaphore(10)) inside the task.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from celery import chord, group

from ...domain.models import Chapter, ChapterStatus, ConversionOptions, Job, JobStatus
from ...infrastructure.adapters.audio_merger import PydubAudioMerger
from ...infrastructure.adapters.epub_reader import EbooklibEpubReader
from ...infrastructure.adapters.redis_store import RedisJobStore
from ...infrastructure.adapters.tts_engine import EdgeTTSEngine
from ...application.services import ConvertChapterService, MergeAudiobookService
from ...infrastructure.logging import get_logger
from .app import celery_app

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/output")
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Chapter conversion task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, queue="chapters", name="audiobook.infrastructure.celery.tasks.convert_chapter")
def convert_chapter(
    self,
    job_id: str,
    chapter_dict: dict,
    options_dict: dict,
) -> Optional[str]:
    """
    Convert one chapter to a FLAC file.
    Returns the path to the FLAC file, or None on error.
    """
    store = RedisJobStore(_REDIS_URL)
    tts = EdgeTTSEngine()
    merger = PydubAudioMerger()
    service = ConvertChapterService(tts, merger, store)

    chapter = Chapter(
        index=chapter_dict["index"],
        title=chapter_dict["title"],
        paragraphs=chapter_dict["paragraphs"],
    )
    options = ConversionOptions(**options_dict)
    work_dir = os.path.join(_OUTPUT_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)

    import time
    t0 = time.monotonic()
    log.info(
        "chapter.start",
        job_id=job_id,
        chapter=chapter.index,
        title=chapter.title,
        paragraphs=len(chapter.paragraphs),
        voice=options.voice,
    )
    try:
        result = asyncio.run(service.execute(job_id, chapter, options, work_dir))
        log.info(
            "chapter.done",
            job_id=job_id,
            chapter=chapter.index,
            duration_s=round(time.monotonic() - t0, 2),
            output=result,
        )
        return result
    except Exception as exc:
        log.error(
            "chapter.error",
            job_id=job_id,
            chapter=chapter.index,
            error=str(exc),
            exc_info=True,
        )
        store.update_chapter(
            job_id, chapter.index, ChapterStatus.ERROR, chapter.progress, error=str(exc)
        )
        return None


# ---------------------------------------------------------------------------
# Merge task  (chord callback — receives list of chapter FLAC paths)
# ---------------------------------------------------------------------------

@celery_app.task(name="audiobook.infrastructure.celery.tasks.merge_audiobook")
def merge_audiobook(
    chapter_files: list[Optional[str]],
    job_id: str,
    book_title: str,
    book_author: str,
    chapter_titles: list[str],
    voice: str,
    cover_path: Optional[str] = None,
) -> Optional[str]:
    """
    Merge all chapter FLAC files into a chaptered M4B.
    Chord passes chapter_files as first positional argument.
    """
    store = RedisJobStore(_REDIS_URL)
    merger = PydubAudioMerger()

    # Filter out failed chapters
    valid_files = [f for f in chapter_files if f and os.path.exists(f)]
    if not valid_files:
        store.update_job_status(job_id, JobStatus.ERROR, error="All chapters failed")
        return None

    work_dir = os.path.join(_OUTPUT_DIR, job_id)
    # Keep titles aligned with valid files (by matching filenames to indices)
    def _idx(path: str) -> int:
        return int(os.path.basename(path).replace("part_", "").replace(".flac", ""))

    sorted_files = sorted(valid_files, key=_idx)
    aligned_titles = [chapter_titles[_idx(f)] for f in sorted_files if _idx(f) < len(chapter_titles)]

    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in book_title)[:50].strip()
    output_path = os.path.join(work_dir, f"{safe_title}.m4b")

    import time
    log.info("merge.start", job_id=job_id, chapters=len(sorted_files))
    store.update_job_status(job_id, JobStatus.MERGING)
    t0 = time.monotonic()

    try:
        merger.make_m4b(
            chapter_files=sorted_files,
            output_path=output_path,
            book_title=book_title,
            book_author=book_author,
            chapter_titles=aligned_titles,
            cover_path=cover_path,
        )
        log.info(
            "merge.done",
            job_id=job_id,
            output=output_path,
            duration_s=round(time.monotonic() - t0, 2),
        )
        store.update_job_status(job_id, JobStatus.DONE, m4b_path=output_path)
        return output_path
    except Exception as exc:
        log.error("merge.error", job_id=job_id, error=str(exc), exc_info=True)
        store.update_job_status(job_id, JobStatus.ERROR, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Dispatch helper  (called from the API route)
# ---------------------------------------------------------------------------

def dispatch_conversion(
    job: Job,
    chapters_with_paragraphs: list[dict],
    options: ConversionOptions,
    cover_path: Optional[str] = None,
) -> None:
    """
    Build and fire the Celery chord:
      group(convert_chapter × N)  →  merge_audiobook
    """
    chapter_tasks = group(
        convert_chapter.s(
            job.id,
            {
                "index": ch["index"],
                "title": ch["title"],
                "paragraphs": ch["paragraphs"],
            },
            {
                "voice": options.voice,
                "sentence_pause_ms": options.sentence_pause_ms,
                "paragraph_pause_ms": options.paragraph_pause_ms,
                "chapter_pause_ms": options.chapter_pause_ms,
            },
        )
        for ch in chapters_with_paragraphs
    )

    chapter_titles = [ch["title"] for ch in chapters_with_paragraphs]

    pipeline = chord(
        chapter_tasks,
        merge_audiobook.s(
            job.id,
            job.book_title,
            job.book_author,
            chapter_titles,
            options.voice,
            cover_path,
        ),
    )
    pipeline.apply_async()
