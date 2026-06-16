"""
Ports (abstract interfaces) — the boundary between domain/application and infrastructure.
Infrastructure adapters must implement these contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from .models import Chapter, ChapterStatus, Job, JobStatus


# ---------------------------------------------------------------------------
# Storage port
# ---------------------------------------------------------------------------

class IJobStore(ABC):
    """Persistence port for conversion jobs."""

    @abstractmethod
    def save(self, job: Job) -> None:
        """Persist a new job (or overwrite)."""

    @abstractmethod
    def get(self, job_id: str) -> Optional[Job]:
        """Return the job or None if not found."""

    @abstractmethod
    def update_chapter(
        self,
        job_id: str,
        chapter_index: int,
        status: ChapterStatus,
        progress: float,
        file_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Atomically update a chapter's progress and status."""

    @abstractmethod
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        m4b_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update the overall job status."""


# ---------------------------------------------------------------------------
# Progress bus port  (used by API for SSE streaming)
# ---------------------------------------------------------------------------

class IProgressBus(ABC):
    """Async pub/sub bus for real-time progress updates."""

    @abstractmethod
    async def publish(self, job_id: str, payload: dict) -> None:
        """Publish a progress event for a job."""

    @abstractmethod
    async def subscribe(self, job_id: str) -> AsyncIterator[dict]:
        """Async-iterate progress events for a job."""


# ---------------------------------------------------------------------------
# TTS port
# ---------------------------------------------------------------------------

class ITTSEngine(ABC):
    """Synthesizes text to audio files."""

    @abstractmethod
    async def synthesize_text(
        self,
        text: str,
        voice: str,
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        """Synthesize a single piece of text to a FLAC file."""

    @abstractmethod
    async def synthesize_paragraph(
        self,
        paragraph: str,
        voice: str,
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        """
        Synthesize a paragraph (handles sentence splitting and concurrent requests
        internally) and write the combined result to a FLAC file.
        """

    @abstractmethod
    async def list_voices(self) -> list[dict]:
        """Return all available voices as a list of dicts."""


# ---------------------------------------------------------------------------
# Audio merger port
# ---------------------------------------------------------------------------

class IAudioMerger(ABC):
    """Assembles audio segments and produces the final M4B."""

    @abstractmethod
    def concatenate(
        self,
        input_files: list[str],
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        """Concatenate audio files sequentially into one output file."""

    @abstractmethod
    def make_m4b(
        self,
        chapter_files: list[str],
        output_path: str,
        book_title: str,
        book_author: str,
        chapter_titles: list[str],
        cover_path: Optional[str] = None,
    ) -> None:
        """Merge chapter FLAC files into a chaptered M4B audiobook."""


# ---------------------------------------------------------------------------
# EPUB reader port
# ---------------------------------------------------------------------------

class IEpubReader(ABC):
    """Reads an EPUB file and converts it to the intermediate TXT format."""

    @abstractmethod
    def to_txt(self, epub_path: str) -> tuple[str, str, str]:
        """
        Parse an EPUB and return (txt_content, book_title, book_author).
        txt_content follows the epub2tts-edge format:
          Title: …\\nAuthor: …\\n\\n# Chapter\\n\\nparagraph…
        """

    @abstractmethod
    def parse_txt(self, txt_content: str) -> tuple[list[Chapter], str, str]:
        """
        Parse the intermediate TXT format into structured chapters.
        Returns (chapters, book_title, book_author).
        """
