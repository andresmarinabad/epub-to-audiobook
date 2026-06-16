"""Pydantic I/O schemas for the HTTP API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# EPUB / TXT parsing
# ---------------------------------------------------------------------------

class ParseEpubResponse(BaseModel):
    txt_content: str
    book_title: str
    book_author: str
    cover_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Job creation
# ---------------------------------------------------------------------------

class StartJobRequest(BaseModel):
    txt_content: str = Field(..., description="Edited TXT content in epub2tts-edge format")
    voice: str = Field("en-US-AndrewNeural", description="Edge TTS voice short name")
    sentence_pause_ms: int = Field(1200, ge=0, le=10_000)
    paragraph_pause_ms: int = Field(1500, ge=0, le=10_000)
    chapter_pause_ms: int = Field(2000, ge=0, le=10_000)
    cover_path: Optional[str] = None


class StartJobResponse(BaseModel):
    job_id: str
    total_chapters: int
    book_title: str
    book_author: str


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

class ChapterState(BaseModel):
    index: int
    title: str
    status: str
    progress: float
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    overall_progress: float
    book_title: str
    book_author: str
    voice: str
    total_chapters: int
    chapters: list[ChapterState]
    error: Optional[str] = None
    m4b_ready: bool = False


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

class VoiceItem(BaseModel):
    short_name: str
    friendly_name: str
    locale: str
    gender: str
