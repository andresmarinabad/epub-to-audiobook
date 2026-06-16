"""Tests for /api/jobs endpoints — store is mocked."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from audiobook.domain.models import Chapter, ChapterStatus, Job, JobStatus
from audiobook.infrastructure.api.deps import get_job_store
from audiobook.infrastructure.api.main import app

HEADERS = {"X-API-Key": "test-key"}


def _done_job() -> Job:
    ch = Chapter(index=0, title="Intro", paragraphs=[], status=ChapterStatus.DONE, progress=1.0)
    job = Job.create("My Audiobook", "Author", [ch], "en-US-Voice")
    job.status = JobStatus.DONE
    job.m4b_path = "/tmp/book.m4b"
    return job


def _processing_job() -> Job:
    chapters = [
        Chapter(index=0, title="Ch1", paragraphs=[], status=ChapterStatus.DONE, progress=1.0),
        Chapter(index=1, title="Ch2", paragraphs=[], status=ChapterStatus.PROCESSING, progress=0.4),
    ]
    job = Job.create("WIP Book", "Author", chapters, "en-US-Voice")
    job.status = JobStatus.PROCESSING
    return job


@pytest.fixture
def store_client(client):
    """Client with a mocked job store injected."""
    mock_store = MagicMock()
    app.dependency_overrides[get_job_store] = lambda: mock_store
    yield client, mock_store
    # conftest fixture already clears overrides, but remove ours too to be safe
    app.dependency_overrides.pop(get_job_store, None)


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

def test_get_job_not_found_returns_404(store_client):
    client, store = store_client
    store.get.return_value = None
    res = client.get("/api/jobs/missing-id", headers=HEADERS)
    assert res.status_code == 404


def test_get_job_returns_200_when_found(store_client):
    client, store = store_client
    job = _done_job()
    store.get.return_value = job
    res = client.get(f"/api/jobs/{job.id}", headers=HEADERS)
    assert res.status_code == 200


def test_get_job_response_schema(store_client):
    client, store = store_client
    job = _done_job()
    store.get.return_value = job
    data = client.get(f"/api/jobs/{job.id}", headers=HEADERS).json()
    assert data["job_id"] == job.id
    assert data["status"] == "done"
    assert data["book_title"] == "My Audiobook"
    assert data["book_author"] == "Author"
    assert data["total_chapters"] == 1
    assert isinstance(data["chapters"], list)


def test_get_job_m4b_ready_when_done(store_client):
    client, store = store_client
    job = _done_job()
    store.get.return_value = job
    data = client.get(f"/api/jobs/{job.id}", headers=HEADERS).json()
    assert data["m4b_ready"] is True


def test_get_job_m4b_not_ready_when_processing(store_client):
    client, store = store_client
    job = _processing_job()
    store.get.return_value = job
    data = client.get(f"/api/jobs/{job.id}", headers=HEADERS).json()
    assert data["m4b_ready"] is False


def test_get_job_overall_progress(store_client):
    client, store = store_client
    job = _processing_job()
    store.get.return_value = job
    data = client.get(f"/api/jobs/{job.id}", headers=HEADERS).json()
    assert data["overall_progress"] == pytest.approx(0.7)


def test_get_job_chapter_states(store_client):
    client, store = store_client
    job = _processing_job()
    store.get.return_value = job
    chapters = client.get(f"/api/jobs/{job.id}", headers=HEADERS).json()["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["status"] == "done"
    assert chapters[1]["status"] == "processing"
    assert chapters[1]["progress"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# POST /api/jobs — validation
# ---------------------------------------------------------------------------

def test_start_job_missing_txt_returns_422(store_client):
    client, _ = store_client
    res = client.post("/api/jobs", json={"voice": "v"}, headers=HEADERS)
    assert res.status_code == 422


def test_start_job_with_no_chapters_returns_422(store_client):
    client, store = store_client
    store.save = MagicMock()
    with patch("audiobook.infrastructure.api.routes.jobs.dispatch_conversion"):
        with patch("audiobook.infrastructure.api.routes.jobs.ParseEpubService") as mock_svc:
            mock_svc.return_value.parse_txt.return_value = ([], "T", "A")
            res = client.post(
                "/api/jobs",
                json={"txt_content": "empty", "voice": "v"},
                headers=HEADERS,
            )
    assert res.status_code == 422


def test_start_job_dispatches_and_returns_job_id(store_client):
    client, store = store_client
    store.save = MagicMock()

    chapters_data = [
        Chapter(index=0, title="Ch1", paragraphs=["Hello."]),
    ]
    with patch("audiobook.infrastructure.api.routes.jobs.dispatch_conversion") as mock_dispatch, \
         patch("audiobook.infrastructure.api.routes.jobs.ParseEpubService") as mock_svc:
        mock_svc.return_value.parse_txt.return_value = (chapters_data, "Book", "Author")
        res = client.post(
            "/api/jobs",
            json={"txt_content": "Title: Book\nAuthor: Author\n\n# Ch1\n\nHello.\n", "voice": "en-US-Test"},
            headers=HEADERS,
        )

    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["total_chapters"] == 1
    mock_dispatch.assert_called_once()
