"""Tests for application services — all external deps mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from audiobook.domain.models import Chapter, ChapterStatus, ConversionOptions, Job, JobStatus
from audiobook.application.services import ConvertChapterService, ParseEpubService


# ---------------------------------------------------------------------------
# ParseEpubService
# ---------------------------------------------------------------------------

def test_parse_epub_service_delegates_to_reader():
    reader = MagicMock()
    reader.parse_txt.return_value = ([], "Title", "Author")
    service = ParseEpubService(reader)

    chapters, title, author = service.parse_txt("some text")

    reader.parse_txt.assert_called_once_with("some text")
    assert title == "Title"
    assert author == "Author"


def test_parse_epub_service_from_file_delegates_to_reader():
    reader = MagicMock()
    reader.to_txt.return_value = ("txt", "Book", "Auth")
    service = ParseEpubService(reader)

    result = service.from_file("/tmp/book.epub")

    reader.to_txt.assert_called_once_with("/tmp/book.epub")
    assert result == ("txt", "Book", "Auth")


# ---------------------------------------------------------------------------
# ConvertChapterService
# ---------------------------------------------------------------------------

def _make_service(tmp_path):
    tts = AsyncMock()
    merger = MagicMock()
    store = MagicMock()

    async def fake_synth(text, voice, path, end_silence_ms=0):
        open(path, "wb").close()

    def fake_concat(files, out, end_silence_ms=0):
        open(out, "wb").close()

    tts.synthesize_text.side_effect = fake_synth
    tts.synthesize_paragraph.side_effect = fake_synth
    merger.concatenate.side_effect = fake_concat

    service = ConvertChapterService(tts, merger, store)
    return service, tts, merger, store


@pytest.mark.asyncio
async def test_execute_returns_flac_path(tmp_path):
    service, *_ = _make_service(tmp_path)
    chapter = Chapter(index=0, title="Intro", paragraphs=["Hello world."])
    options = ConversionOptions(voice="en-US-Test")

    result = await service.execute("job-123", chapter, options, str(tmp_path))

    expected = str(tmp_path / "part_0000.flac")
    assert result == expected


@pytest.mark.asyncio
async def test_execute_marks_chapter_done(tmp_path):
    service, _, _, store = _make_service(tmp_path)
    chapter = Chapter(index=2, title="Middle", paragraphs=["Para one.", "Para two."])
    options = ConversionOptions(voice="en-US-Test")

    await service.execute("job-abc", chapter, options, str(tmp_path))

    # Last update_chapter call must be DONE with progress 1.0
    last_call = store.update_chapter.call_args_list[-1]
    assert last_call.args[2] == ChapterStatus.DONE
    assert last_call.args[3] == 1.0


@pytest.mark.asyncio
async def test_execute_calls_tts_for_each_paragraph(tmp_path):
    service, tts, _, _ = _make_service(tmp_path)
    chapter = Chapter(index=0, title="blank", paragraphs=["P1.", "P2.", "P3."])
    options = ConversionOptions(voice="en-US-Test")

    await service.execute("job-xyz", chapter, options, str(tmp_path))

    assert tts.synthesize_paragraph.call_count == 3


@pytest.mark.asyncio
async def test_execute_synthesizes_title_audio_when_not_blank(tmp_path):
    service, tts, _, _ = _make_service(tmp_path)
    chapter = Chapter(index=0, title="Introduction", paragraphs=["Content."])
    options = ConversionOptions(voice="en-US-Test")

    await service.execute("job-xyz", chapter, options, str(tmp_path))

    tts.synthesize_text.assert_called_once()


@pytest.mark.asyncio
async def test_execute_skips_title_audio_for_blank(tmp_path):
    service, tts, _, _ = _make_service(tmp_path)
    chapter = Chapter(index=0, title="blank", paragraphs=["Content."])
    options = ConversionOptions(voice="en-US-Test")

    await service.execute("job-xyz", chapter, options, str(tmp_path))

    tts.synthesize_text.assert_not_called()


@pytest.mark.asyncio
async def test_execute_calls_merger_concatenate(tmp_path):
    service, _, merger, _ = _make_service(tmp_path)
    chapter = Chapter(index=0, title="Ch", paragraphs=["Para."])
    options = ConversionOptions(voice="v")

    await service.execute("job-1", chapter, options, str(tmp_path))

    merger.concatenate.assert_called_once()


@pytest.mark.asyncio
async def test_execute_publishes_progress_updates(tmp_path):
    tts = AsyncMock()
    merger = MagicMock()
    store = MagicMock()
    bus = AsyncMock()

    async def fake_synth(text, voice, path, end_silence_ms=0):
        open(path, "wb").close()

    def fake_concat(files, out, end_silence_ms=0):
        open(out, "wb").close()

    tts.synthesize_paragraph.side_effect = fake_synth
    merger.concatenate.side_effect = fake_concat

    service = ConvertChapterService(tts, merger, store, bus)
    chapter = Chapter(index=0, title="blank", paragraphs=["P1.", "P2."])
    await service.execute("job-pub", chapter, ConversionOptions(voice="v"), str(tmp_path))

    assert bus.publish.call_count >= 3  # start + 1 per para + done
