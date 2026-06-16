"""Tests for EbooklibEpubReader.parse_txt and extract_cover."""
from __future__ import annotations

import pytest
from audiobook.infrastructure.adapters.epub_reader import EbooklibEpubReader, extract_cover

SAMPLE_TXT = """\
Title: The Great Novel
Author: Jane Doe

# Title

The Great Novel, by Jane Doe

# Chapter One

This is the first paragraph of chapter one.

Here is the second paragraph of chapter one.

# Chapter Two

Content of the second chapter goes here.

# Part 3

Third part with no special name.
"""

MINIMAL_TXT = """\
Title: Short
Author: Me

# Only Chapter

A single paragraph.
"""


# ---------------------------------------------------------------------------
# parse_txt — title / author extraction
# ---------------------------------------------------------------------------

def test_parse_txt_extracts_title():
    reader = EbooklibEpubReader()
    _, title, _ = reader.parse_txt(SAMPLE_TXT)
    assert title == "The Great Novel"


def test_parse_txt_extracts_author():
    reader = EbooklibEpubReader()
    _, _, author = reader.parse_txt(SAMPLE_TXT)
    assert author == "Jane Doe"


def test_parse_txt_defaults_when_no_header():
    reader = EbooklibEpubReader()
    _, title, author = reader.parse_txt("# Ch\n\nHello.\n")
    assert title == "Unknown"
    assert author == "Unknown"


# ---------------------------------------------------------------------------
# parse_txt — chapter structure
# ---------------------------------------------------------------------------

def test_parse_txt_chapter_count():
    reader = EbooklibEpubReader()
    chapters, _, _ = reader.parse_txt(SAMPLE_TXT)
    titles = [c.title for c in chapters]
    assert "Title" in titles
    assert "Chapter One" in titles
    assert "Chapter Two" in titles
    assert "Part 3" in titles


def test_parse_txt_sequential_indices():
    reader = EbooklibEpubReader()
    chapters, _, _ = reader.parse_txt(SAMPLE_TXT)
    for i, ch in enumerate(chapters):
        assert ch.index == i


def test_parse_txt_paragraphs_non_empty():
    reader = EbooklibEpubReader()
    chapters, _, _ = reader.parse_txt(SAMPLE_TXT)
    ch_one = next(c for c in chapters if c.title == "Chapter One")
    assert len(ch_one.paragraphs) >= 1
    assert all(p.strip() for p in ch_one.paragraphs)


def test_parse_txt_empty_input():
    reader = EbooklibEpubReader()
    chapters, title, author = reader.parse_txt("")
    assert chapters == []
    assert title == "Unknown"
    assert author == "Unknown"


def test_parse_txt_minimal():
    reader = EbooklibEpubReader()
    chapters, title, author = reader.parse_txt(MINIMAL_TXT)
    assert title == "Short"
    assert author == "Me"
    assert len(chapters) == 1
    assert chapters[0].title == "Only Chapter"


def test_parse_txt_skips_blank_only_paragraphs():
    txt = "Title: T\nAuthor: A\n\n# Ch\n\n   \n\nReal content here.\n\n   \n\n"
    reader = EbooklibEpubReader()
    chapters, _, _ = reader.parse_txt(txt)
    assert len(chapters) == 1
    for p in chapters[0].paragraphs:
        assert p.strip()


# ---------------------------------------------------------------------------
# extract_cover — graceful failures
# ---------------------------------------------------------------------------

def test_extract_cover_returns_none_for_invalid_epub(tmp_path):
    fake_epub = tmp_path / "fake.epub"
    fake_epub.write_bytes(b"not a real epub")
    result = extract_cover(str(fake_epub), str(tmp_path / "covers"))
    assert result is None


def test_extract_cover_returns_none_for_missing_file(tmp_path):
    result = extract_cover(str(tmp_path / "nonexistent.epub"), str(tmp_path / "covers"))
    assert result is None
