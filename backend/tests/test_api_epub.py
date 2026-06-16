"""Tests for /api/epub/parse endpoint."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

HEADERS = {"X-API-Key": "test-key"}
FAKE_EPUB = b"PK\x03\x04fake epub bytes"


def _mock_parse(from_file_return=("Title: T\nAuthor: A\n\n# Ch\n\nHello.\n", "T", "A")):
    """Context managers to mock the two external calls in the epub route."""
    patch_svc = patch(
        "audiobook.infrastructure.api.routes.epub.ParseEpubService",
    )
    patch_cover = patch(
        "audiobook.infrastructure.api.routes.epub.extract_cover",
        return_value=None,
    )
    patch_settings = patch(
        "audiobook.infrastructure.api.routes.epub.get_settings",
        return_value=MagicMock(output_dir="/tmp/test-covers"),
    )
    return patch_svc, patch_cover, patch_settings


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_parse_epub_rejects_non_epub(client):
    res = client.post(
        "/api/epub/parse",
        headers=HEADERS,
        files={"file": ("book.txt", b"some text", "text/plain")},
    )
    assert res.status_code == 400


def test_parse_epub_requires_file(client):
    res = client.post("/api/epub/parse", headers=HEADERS)
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_parse_epub_returns_200(client):
    with patch("audiobook.infrastructure.api.routes.epub.ParseEpubService") as mock_svc, \
         patch("audiobook.infrastructure.api.routes.epub.extract_cover", return_value=None), \
         patch("audiobook.infrastructure.api.routes.epub.get_settings",
               return_value=MagicMock(output_dir="/tmp")):
        mock_svc.return_value.from_file.return_value = ("txt", "T", "A")
        res = client.post(
            "/api/epub/parse",
            headers=HEADERS,
            files={"file": ("book.epub", FAKE_EPUB, "application/epub+zip")},
        )
    assert res.status_code == 200


def test_parse_epub_response_fields(client):
    with patch("audiobook.infrastructure.api.routes.epub.ParseEpubService") as mock_svc, \
         patch("audiobook.infrastructure.api.routes.epub.extract_cover", return_value=None), \
         patch("audiobook.infrastructure.api.routes.epub.get_settings",
               return_value=MagicMock(output_dir="/tmp")):
        mock_svc.return_value.from_file.return_value = ("the txt", "My Book", "Jane Doe")
        res = client.post(
            "/api/epub/parse",
            headers=HEADERS,
            files={"file": ("book.epub", FAKE_EPUB, "application/epub+zip")},
        )
    data = res.json()
    assert data["book_title"] == "My Book"
    assert data["book_author"] == "Jane Doe"
    assert data["txt_content"] == "the txt"
    assert "cover_path" in data


def test_parse_epub_includes_cover_path_when_found(client):
    with patch("audiobook.infrastructure.api.routes.epub.ParseEpubService") as mock_svc, \
         patch("audiobook.infrastructure.api.routes.epub.extract_cover",
               return_value="/tmp/.covers/abc.jpg"), \
         patch("audiobook.infrastructure.api.routes.epub.get_settings",
               return_value=MagicMock(output_dir="/tmp")):
        mock_svc.return_value.from_file.return_value = ("txt", "T", "A")
        res = client.post(
            "/api/epub/parse",
            headers=HEADERS,
            files={"file": ("book.epub", FAKE_EPUB, "application/epub+zip")},
        )
    assert res.json()["cover_path"] == "/tmp/.covers/abc.jpg"


def test_parse_epub_cover_path_null_when_no_cover(client):
    with patch("audiobook.infrastructure.api.routes.epub.ParseEpubService") as mock_svc, \
         patch("audiobook.infrastructure.api.routes.epub.extract_cover", return_value=None), \
         patch("audiobook.infrastructure.api.routes.epub.get_settings",
               return_value=MagicMock(output_dir="/tmp")):
        mock_svc.return_value.from_file.return_value = ("txt", "T", "A")
        res = client.post(
            "/api/epub/parse",
            headers=HEADERS,
            files={"file": ("book.epub", FAKE_EPUB, "application/epub+zip")},
        )
    assert res.json()["cover_path"] is None
