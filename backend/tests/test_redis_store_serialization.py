"""Tests for Redis store serialization — no real Redis required."""
from __future__ import annotations

import pytest
from audiobook.domain.models import Chapter, ChapterStatus, Job, JobStatus
from audiobook.infrastructure.adapters.redis_store import _dict_to_job, _job_to_dict


def _make_job(
    title: str = "Test Book",
    author: str = "Author Name",
    status: JobStatus = JobStatus.PENDING,
    m4b_path: str | None = None,
) -> Job:
    chapters = [
        Chapter(index=0, title="Intro", paragraphs=["Hello"], status=ChapterStatus.DONE, progress=1.0),
        Chapter(index=1, title="Ch1", paragraphs=["World"], status=ChapterStatus.PENDING, progress=0.0),
    ]
    job = Job.create(title, author, chapters, "en-US-Voice")
    job.status = status
    job.m4b_path = m4b_path
    return job


def _roundtrip(job: Job) -> Job:
    return _dict_to_job(_job_to_dict(job))


# ---------------------------------------------------------------------------
# Basic field preservation
# ---------------------------------------------------------------------------

def test_roundtrip_book_title():
    assert _roundtrip(_make_job(title="Pride and Prejudice")).book_title == "Pride and Prejudice"


def test_roundtrip_book_author():
    assert _roundtrip(_make_job(author="Jane Austen")).book_author == "Jane Austen"


def test_roundtrip_job_id():
    job = _make_job()
    assert _roundtrip(job).id == job.id


def test_roundtrip_voice():
    job = _make_job()
    assert _roundtrip(job).voice == "en-US-Voice"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", list(JobStatus))
def test_roundtrip_status(status: JobStatus):
    job = _make_job(status=status)
    assert _roundtrip(job).status == status


# ---------------------------------------------------------------------------
# m4b_path
# ---------------------------------------------------------------------------

def test_roundtrip_m4b_path_none():
    assert _roundtrip(_make_job()).m4b_path is None


def test_roundtrip_m4b_path_set():
    path = "/app/output/abc/book.m4b"
    assert _roundtrip(_make_job(m4b_path=path)).m4b_path == path


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

def test_roundtrip_chapter_count():
    job = _make_job()
    result = _roundtrip(job)
    assert len(result.chapters) == 2


def test_roundtrip_chapter_titles():
    job = _make_job()
    result = _roundtrip(job)
    assert result.chapters[0].title == "Intro"
    assert result.chapters[1].title == "Ch1"


def test_roundtrip_chapter_status():
    job = _make_job()
    result = _roundtrip(job)
    assert result.chapters[0].status == ChapterStatus.DONE
    assert result.chapters[1].status == ChapterStatus.PENDING


def test_roundtrip_chapter_progress():
    job = _make_job()
    result = _roundtrip(job)
    assert result.chapters[0].progress == 1.0
    assert result.chapters[1].progress == 0.0


def test_roundtrip_paragraphs_not_persisted():
    """Paragraphs are stripped on serialisation — only needed during conversion."""
    job = _make_job()
    result = _roundtrip(job)
    for ch in result.chapters:
        assert ch.paragraphs == []


# ---------------------------------------------------------------------------
# overall_progress is recomputed from chapters
# ---------------------------------------------------------------------------

def test_roundtrip_overall_progress():
    job = _make_job()
    d = _job_to_dict(job)
    assert d["overall_progress"] == pytest.approx(0.5)
