"""Tests for domain models — no external deps."""
from __future__ import annotations

import pytest
from audiobook.domain.models import Chapter, ChapterStatus, Job, JobStatus


def _chapters(*titles: str) -> list[Chapter]:
    return [Chapter(index=i, title=t, paragraphs=[]) for i, t in enumerate(titles)]


# ---------------------------------------------------------------------------
# Job.create
# ---------------------------------------------------------------------------

def test_job_create_sets_fields():
    chapters = _chapters("Intro", "Ch1")
    job = Job.create("My Book", "Author", chapters, "en-US-Voice")
    assert job.book_title == "My Book"
    assert job.book_author == "Author"
    assert job.voice == "en-US-Voice"
    assert job.status == JobStatus.PENDING
    assert len(job.id) == 36  # UUID4


def test_job_create_unique_ids():
    c = _chapters("Ch")
    j1 = Job.create("Book", "A", c, "v")
    j2 = Job.create("Book", "A", c, "v")
    assert j1.id != j2.id


def test_total_chapters():
    job = Job.create("B", "A", _chapters("1", "2", "3"), "v")
    assert job.total_chapters == 3


def test_total_chapters_empty():
    job = Job.create("B", "A", [], "v")
    assert job.total_chapters == 0


# ---------------------------------------------------------------------------
# overall_progress
# ---------------------------------------------------------------------------

def test_overall_progress_zero():
    chapters = [
        Chapter(index=0, title="Ch1", paragraphs=[], progress=0.0),
        Chapter(index=1, title="Ch2", paragraphs=[], progress=0.0),
    ]
    job = Job.create("B", "A", chapters, "v")
    assert job.overall_progress == 0.0


def test_overall_progress_partial():
    chapters = [
        Chapter(index=0, title="Ch1", paragraphs=[], progress=1.0),
        Chapter(index=1, title="Ch2", paragraphs=[], progress=0.0),
    ]
    job = Job.create("B", "A", chapters, "v")
    assert job.overall_progress == 0.5


def test_overall_progress_complete():
    chapters = [
        Chapter(index=0, title="Ch1", paragraphs=[], progress=1.0),
        Chapter(index=1, title="Ch2", paragraphs=[], progress=1.0),
    ]
    job = Job.create("B", "A", chapters, "v")
    assert job.overall_progress == 1.0


def test_overall_progress_empty_job():
    job = Job.create("B", "A", [], "v")
    assert job.overall_progress == 0.0


# ---------------------------------------------------------------------------
# JobStatus / ChapterStatus enum values
# ---------------------------------------------------------------------------

def test_job_status_values():
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.PROCESSING.value == "processing"
    assert JobStatus.MERGING.value == "merging"
    assert JobStatus.DONE.value == "done"
    assert JobStatus.ERROR.value == "error"


def test_chapter_status_values():
    assert ChapterStatus.PENDING.value == "pending"
    assert ChapterStatus.PROCESSING.value == "processing"
    assert ChapterStatus.DONE.value == "done"
    assert ChapterStatus.ERROR.value == "error"


# ---------------------------------------------------------------------------
# Chapter defaults
# ---------------------------------------------------------------------------

def test_chapter_defaults():
    ch = Chapter(index=0, title="Intro", paragraphs=["Hello"])
    assert ch.status == ChapterStatus.PENDING
    assert ch.progress == 0.0
    assert ch.file_path is None
    assert ch.error is None
