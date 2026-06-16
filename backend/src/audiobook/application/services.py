"""
Application services (use cases).
Only depends on domain models and ports — never on infrastructure.
"""
from __future__ import annotations

import os
from typing import Optional

from ..domain.models import (
    Chapter,
    ChapterStatus,
    ConversionOptions,
    Job,
    JobStatus,
)
from ..domain.ports import IAudioMerger, IEpubReader, IJobStore, IProgressBus, ITTSEngine


# ---------------------------------------------------------------------------
# Parse EPUB use case
# ---------------------------------------------------------------------------

class ParseEpubService:
    def __init__(self, reader: IEpubReader) -> None:
        self._reader = reader

    def from_file(self, epub_path: str) -> tuple[str, str, str]:
        """Return (txt_content, title, author)."""
        return self._reader.to_txt(epub_path)

    def parse_txt(self, txt_content: str) -> tuple[list[Chapter], str, str]:
        """Return (chapters, title, author)."""
        return self._reader.parse_txt(txt_content)


# ---------------------------------------------------------------------------
# Convert single chapter use case  (runs inside each Celery worker)
# ---------------------------------------------------------------------------

class ConvertChapterService:
    def __init__(
        self,
        tts: ITTSEngine,
        merger: IAudioMerger,
        store: IJobStore,
        progress_bus: Optional[IProgressBus] = None,
    ) -> None:
        self._tts = tts
        self._merger = merger
        self._store = store
        self._bus = progress_bus

    async def execute(
        self,
        job_id: str,
        chapter: Chapter,
        options: ConversionOptions,
        work_dir: str,
    ) -> str:
        """
        Synthesize one chapter to a FLAC file and return its path.
        Publishes progress to the store and the bus on every paragraph.
        """
        chapter_dir = os.path.join(work_dir, f"ch_{chapter.index:04d}")
        os.makedirs(chapter_dir, exist_ok=True)

        self._store.update_chapter(job_id, chapter.index, ChapterStatus.PROCESSING, 0.0)
        await self._publish(job_id, chapter.index, "processing", 0.0)

        files_to_merge: list[str] = []

        # Chapter title audio
        if chapter.title and chapter.title not in ("blank", "Title"):
            title_file = os.path.join(chapter_dir, "title.flac")
            await self._tts.synthesize_text(
                chapter.title, options.voice, title_file, end_silence_ms=1200
            )
            files_to_merge.append(title_file)

        total = len(chapter.paragraphs)
        for p_idx, paragraph in enumerate(chapter.paragraphs):
            is_last = p_idx == total - 1
            pause = options.chapter_pause_ms if is_last else options.paragraph_pause_ms
            p_file = os.path.join(chapter_dir, f"p{p_idx:04d}.flac")
            await self._tts.synthesize_paragraph(
                paragraph, options.voice, p_file, end_silence_ms=pause
            )
            files_to_merge.append(p_file)

            progress = (p_idx + 1) / total
            self._store.update_chapter(job_id, chapter.index, ChapterStatus.PROCESSING, progress)
            await self._publish(job_id, chapter.index, "processing", progress)

        # Merge paragraph files → chapter FLAC
        chapter_flac = os.path.join(work_dir, f"part_{chapter.index:04d}.flac")
        self._merger.concatenate(files_to_merge, chapter_flac)

        for f in files_to_merge:
            if os.path.exists(f):
                os.remove(f)
        try:
            os.rmdir(chapter_dir)
        except OSError:
            pass

        self._store.update_chapter(
            job_id, chapter.index, ChapterStatus.DONE, 1.0, file_path=chapter_flac
        )
        await self._publish(job_id, chapter.index, "done", 1.0)
        return chapter_flac

    async def _publish(
        self, job_id: str, chapter_index: int, status: str, progress: float
    ) -> None:
        if self._bus:
            await self._bus.publish(
                job_id,
                {"chapter_index": chapter_index, "status": status, "progress": progress},
            )


# ---------------------------------------------------------------------------
# Merge audiobook use case  (runs after all chapters are done)
# ---------------------------------------------------------------------------

class MergeAudiobookService:
    def __init__(
        self,
        merger: IAudioMerger,
        store: IJobStore,
        progress_bus: Optional[IProgressBus] = None,
    ) -> None:
        self._merger = merger
        self._store = store
        self._bus = progress_bus

    async def execute(
        self,
        job: Job,
        chapter_files: list[str],
        output_path: str,
    ) -> str:
        """Merge chapter FLACs into a chaptered M4B and update the job status."""
        self._store.update_job_status(job.id, JobStatus.MERGING)
        if self._bus:
            await self._bus.publish(job.id, {"status": "merging"})

        chapter_titles = [c.title for c in job.chapters]
        self._merger.make_m4b(
            chapter_files=chapter_files,
            output_path=output_path,
            book_title=job.book_title,
            book_author=job.book_author,
            chapter_titles=chapter_titles,
        )

        self._store.update_job_status(job.id, JobStatus.DONE, m4b_path=output_path)
        if self._bus:
            await self._bus.publish(job.id, {"status": "done", "m4b_path": output_path})

        return output_path
