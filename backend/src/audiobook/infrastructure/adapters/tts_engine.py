"""
Adapter: ITTSEngine → edge-tts (Microsoft Edge TTS).
Handles sentence splitting, concurrent synthesis (semaphore=10), and retry logic.
"""
from __future__ import annotations

import asyncio
import os
import re
import time

import edge_tts
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment

from ...domain.ports import ITTSEngine

_MULTI_EXCL = re.compile(r"[!]+")
_MULTI_QMARK = re.compile(r"[?]+")
_MAX_CONCURRENT = 10  # Edge TTS connection limit per chapter
_RETRY_ATTEMPTS = 3
_RETRY_SLEEP = 3


def _normalise(text: str) -> str:
    text = _MULTI_EXCL.sub("!", text)
    text = _MULTI_QMARK.sub("?", text)
    return text.strip()


async def _synthesize_one(text: str, voice: str, path: str) -> None:
    """Synthesize a single sentence with retries."""
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            communicate = edge_tts.Communicate(_normalise(text), voice)
            await communicate.save(path)
            if os.path.getsize(path) == 0:
                raise RuntimeError("edge-tts returned empty file")
            return
        except Exception as exc:
            if attempt < _RETRY_ATTEMPTS - 1:
                await asyncio.sleep(_RETRY_SLEEP)
            else:
                raise RuntimeError(
                    f"edge-tts failed after {_RETRY_ATTEMPTS} attempts: {exc}"
                ) from exc


async def _synthesize_batch(
    texts: list[str], voice: str, paths: list[str]
) -> None:
    """Synthesize a list of sentences concurrently (bounded by semaphore)."""
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _bounded(text: str, path: str) -> None:
        async with sem:
            await _synthesize_one(text, voice, path)

    await asyncio.gather(*[_bounded(t, p) for t, p in zip(texts, paths)])


class EdgeTTSEngine(ITTSEngine):

    async def synthesize_text(
        self,
        text: str,
        voice: str,
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        tmp = output_path + ".tmp.mp3"
        await _synthesize_one(text, voice, tmp)
        _to_flac(tmp, output_path, end_silence_ms)

    async def synthesize_paragraph(
        self,
        paragraph: str,
        voice: str,
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        sentences = [s for s in sent_tokenize(paragraph) if any(c.isalnum() for c in s)]
        if not sentences:
            # Write silence only
            AudioSegment.silent(end_silence_ms or 100).export(output_path, format="flac")
            return

        base = output_path + "_s"
        tmp_files = [f"{base}{i:04d}.mp3" for i in range(len(sentences))]
        await _synthesize_batch(sentences, voice, tmp_files)

        # Combine sentences then add paragraph silence
        combined = AudioSegment.empty()
        for f in tmp_files:
            combined += AudioSegment.from_file(f)
            os.remove(f)
        if end_silence_ms:
            combined += AudioSegment.silent(end_silence_ms)
        combined.export(output_path, format="flac")

    async def list_voices(self) -> list[dict]:
        voices = await edge_tts.list_voices()
        return [
            {
                "short_name": v["ShortName"],
                "friendly_name": v["FriendlyName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
            }
            for v in voices
        ]


def _to_flac(mp3_path: str, flac_path: str, end_silence_ms: int) -> None:
    audio = AudioSegment.from_file(mp3_path)
    if end_silence_ms:
        audio += AudioSegment.silent(end_silence_ms)
    audio.export(flac_path, format="flac")
    os.remove(mp3_path)
