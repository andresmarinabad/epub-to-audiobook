"""
Domain entities and value objects.
Zero external dependencies — pure Python dataclasses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    MERGING = "merging"
    DONE = "done"
    ERROR = "error"


class ChapterStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class Chapter:
    index: int
    title: str
    paragraphs: list[str]
    status: ChapterStatus = ChapterStatus.PENDING
    progress: float = 0.0
    file_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ConversionOptions:
    voice: str
    sentence_pause_ms: int = 1200
    paragraph_pause_ms: int = 1500
    chapter_pause_ms: int = 2000


@dataclass
class Job:
    id: str
    book_title: str
    book_author: str
    voice: str
    chapters: list[Chapter]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    m4b_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def overall_progress(self) -> float:
        if not self.chapters:
            return 0.0
        return sum(c.progress for c in self.chapters) / len(self.chapters)

    @classmethod
    def create(
        cls,
        book_title: str,
        book_author: str,
        chapters: list[Chapter],
        voice: str,
    ) -> "Job":
        return cls(
            id=str(uuid.uuid4()),
            book_title=book_title,
            book_author=book_author,
            voice=voice,
            chapters=chapters,
        )
