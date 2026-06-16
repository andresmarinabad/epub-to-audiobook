"""
Adapter: IAudioMerger → pydub + ffmpeg.
Concatenates FLAC segments and assembles the final chaptered M4B.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from pydub import AudioSegment

from ...domain.ports import IAudioMerger

_SAFE_FILENAME = re.compile(r'[^\w\s\-.]')


class PydubAudioMerger(IAudioMerger):

    def concatenate(
        self,
        input_files: list[str],
        output_path: str,
        end_silence_ms: int = 0,
    ) -> None:
        combined = AudioSegment.empty()
        for f in input_files:
            combined += AudioSegment.from_file(f)
        if end_silence_ms:
            combined += AudioSegment.silent(end_silence_ms)
        combined.export(output_path, format="flac")

    def make_m4b(
        self,
        chapter_files: list[str],
        output_path: str,
        book_title: str,
        book_author: str,
        chapter_titles: list[str],
        cover_path: Optional[str] = None,
    ) -> None:
        work_dir = os.path.dirname(output_path)
        filelist = os.path.join(work_dir, "filelist.txt")
        metadata_file = os.path.join(work_dir, "FFMETADATAFILE")
        tmp_m4a = output_path.replace(".m4b", ".m4a")

        # Write ffmpeg concat list
        with open(filelist, "w") as f:
            for cf in chapter_files:
                escaped = cf.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        # Write chapter metadata
        _write_ffmetadata(metadata_file, book_title, book_author, chapter_files, chapter_titles)

        # Step 1: concat FLAC → M4A (lossless copy)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", filelist,
                "-codec:a", "flac", "-f", "mp4", "-strict", "-2",
                tmp_m4a,
            ],
            check=True,
            capture_output=True,
        )

        # Step 2: M4A + metadata (+ optional cover) → M4B (AAC)
        use_cover = bool(cover_path and os.path.exists(cover_path))
        if use_cover:
            # cover is input 1, metadata is input 2
            step2_cmd = [
                "ffmpeg", "-y",
                "-i", tmp_m4a,
                "-i", cover_path,
                "-i", metadata_file,
                "-map", "0:a",
                "-map", "1:v",
                "-map_metadata", "2",
                "-c:a", "aac",
                "-c:v", "copy",
                "-disposition:v:0", "attached_pic",
                output_path,
            ]
        else:
            step2_cmd = [
                "ffmpeg", "-y",
                "-i", tmp_m4a,
                "-i", metadata_file,
                "-map_metadata", "1",
                "-codec", "aac",
                output_path,
            ]
        subprocess.run(step2_cmd, check=True, capture_output=True)

        # Cleanup
        for path in (filelist, metadata_file, tmp_m4a):
            if os.path.exists(path):
                os.remove(path)
        for cf in chapter_files:
            if os.path.exists(cf):
                os.remove(cf)


def _write_ffmetadata(
    path: str,
    title: str,
    author: str,
    chapter_files: list[str],
    chapter_titles: list[str],
) -> None:
    start_ms = 0
    with open(path, "w") as f:
        f.write(";FFMETADATA1\n")
        f.write(f"ARTIST={author}\n")
        f.write(f"ALBUM={title}\n")
        f.write(f"TITLE={title}\n")
        for i, cf in enumerate(chapter_files):
            audio = AudioSegment.from_file(cf)
            duration_ms = len(audio)
            chap_title = chapter_titles[i] if i < len(chapter_titles) else f"Chapter {i+1}"
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={start_ms}\n")
            f.write(f"END={start_ms + duration_ms}\n")
            f.write(f"title={chap_title}\n")
            start_ms += duration_ms
