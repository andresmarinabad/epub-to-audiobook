"""Tests for ffmetadata generation — mocks AudioSegment so ffmpeg is not required."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from audiobook.infrastructure.adapters.audio_merger import _write_ffmetadata


def _mock_segments(*durations_ms: int):
    """Return a sequence of MagicMock AudioSegments with given durations."""
    segs = []
    for d in durations_ms:
        m = MagicMock()
        m.__len__ = lambda self, _d=d: _d
        segs.append(m)
    return segs


@pytest.fixture
def meta_path(tmp_path):
    return str(tmp_path / "FFMETADATA")


def _write(meta_path, titles, durations):
    fakes = _mock_segments(*durations)
    with patch(
        "audiobook.infrastructure.adapters.audio_merger.AudioSegment.from_file",
        side_effect=fakes,
    ):
        chapter_files = [f"ch{i}.flac" for i in range(len(durations))]
        _write_ffmetadata(meta_path, "My Book", "Jane Doe", chapter_files, titles)
    return open(meta_path).read()


# ---------------------------------------------------------------------------
# Header block
# ---------------------------------------------------------------------------

def test_ffmetadata_header(meta_path):
    content = _write(meta_path, ["Ch1"], [1000])
    assert content.startswith(";FFMETADATA1")


def test_ffmetadata_album(meta_path):
    content = _write(meta_path, ["Ch1"], [1000])
    assert "ALBUM=My Book" in content


def test_ffmetadata_artist(meta_path):
    content = _write(meta_path, ["Ch1"], [1000])
    assert "ARTIST=Jane Doe" in content


def test_ffmetadata_title(meta_path):
    content = _write(meta_path, ["Ch1"], [1000])
    assert "TITLE=My Book" in content


# ---------------------------------------------------------------------------
# Chapter blocks
# ---------------------------------------------------------------------------

def test_ffmetadata_chapter_markers(meta_path):
    content = _write(meta_path, ["Intro", "Main"], [2000, 3000])
    assert content.count("[CHAPTER]") == 2


def test_ffmetadata_chapter_titles(meta_path):
    content = _write(meta_path, ["Prologue", "Epilogue"], [1000, 1000])
    assert "title=Prologue" in content
    assert "title=Epilogue" in content


def test_ffmetadata_first_chapter_starts_at_zero(meta_path):
    content = _write(meta_path, ["Ch1"], [5000])
    assert "START=0" in content


def test_ffmetadata_first_chapter_end(meta_path):
    content = _write(meta_path, ["Ch1"], [5000])
    assert "END=5000" in content


def test_ffmetadata_chapter_continuity(meta_path):
    content = _write(meta_path, ["Ch1", "Ch2"], [3000, 4000])
    # Ch1: 0–3000, Ch2: 3000–7000
    assert "START=0" in content
    assert "END=3000" in content
    assert "START=3000" in content
    assert "END=7000" in content


def test_ffmetadata_timebase(meta_path):
    content = _write(meta_path, ["Ch1"], [1000])
    assert "TIMEBASE=1/1000" in content


# ---------------------------------------------------------------------------
# Fallback chapter title
# ---------------------------------------------------------------------------

def test_ffmetadata_fallback_title_when_list_too_short(meta_path):
    content = _write(meta_path, [], [2000])  # no titles provided
    assert "title=Chapter 1" in content
