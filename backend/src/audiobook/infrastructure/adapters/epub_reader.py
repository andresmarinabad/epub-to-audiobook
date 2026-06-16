"""
Adapter: IEpubReader → ebooklib + BeautifulSoup + NLTK.
Replicates epub2tts-edge parsing logic.
"""
from __future__ import annotations

import io
import os
import re
import uuid
import warnings
import zipfile
from typing import Optional

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
from lxml import etree
from nltk.tokenize import sent_tokenize
from PIL import Image

from ...domain.models import Chapter, ChapterStatus
from ...domain.ports import IEpubReader

warnings.filterwarnings("ignore", module="ebooklib.epub")

_NS = {
    "calibre": "http://calibre.kovidgoyal.net/2009/metadata",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf",
    "u": "urn:oasis:names:tc:opendocument:xmlns:container",
}

_CLEAN_WS = re.compile(r"[\s\n]+")
_CURLY_DBL = re.compile(r"[“”]")
_CURLY_SGL = re.compile(r"[‘’]")


def _clean(text: str) -> str:
    text = _CLEAN_WS.sub(" ", text)
    text = _CURLY_DBL.sub('"', text)
    text = _CURLY_SGL.sub("'", text)
    return text.strip()


def _chap_to_text(content: bytes) -> tuple[Optional[str], list[str]]:
    soup = BeautifulSoup(content, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else None

    # Drop pure-number footnote links
    for a in soup.find_all("a", href=True):
        if not any(c.isalpha() for c in a.get_text()):
            a.decompose()

    paragraphs = soup.find_all("p") or soup.find_all("div")
    return title, [_clean("".join(p.strings)) for p in paragraphs if "".join(p.strings).strip()]


def extract_cover(epub_path: str, covers_dir: str) -> Optional[str]:
    """
    Try to extract the cover image from an EPUB and save it as a JPEG.
    Returns the saved path, or None if no cover is found.
    Tries three strategies in order: ITEM_COVER type, OPF metadata reference,
    and any image with 'cover' in its name.
    """
    try:
        book = epub.read_epub(epub_path)
        cover_bytes: Optional[bytes] = None

        # Strategy 1: dedicated cover item type
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                cover_bytes = item.get_content()
                break

        # Strategy 2: OPF metadata cover reference by id
        if cover_bytes is None:
            meta = book.get_metadata("OPF", "cover")
            if meta:
                cid = meta[0][1].get("content")
                if cid:
                    item = book.get_item_with_id(cid)
                    if item:
                        cover_bytes = item.get_content()

        # Strategy 3: any image whose name contains "cover"
        if cover_bytes is None:
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE and "cover" in item.get_name().lower():
                    cover_bytes = item.get_content()
                    break

        if cover_bytes is None:
            return None

        os.makedirs(covers_dir, exist_ok=True)
        out = os.path.join(covers_dir, f"{uuid.uuid4()}.jpg")
        img = Image.open(io.BytesIO(cover_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=90)
        return out
    except Exception:
        return None


class EbooklibEpubReader(IEpubReader):

    def to_txt(self, epub_path: str) -> tuple[str, str, str]:
        book = epub.read_epub(epub_path)
        title = book.get_metadata("DC", "title")[0][0]
        author = book.get_metadata("DC", "creator")[0][0]

        spine_ids = [sid for sid, linear in book.spine if linear == "yes"]
        items = {
            item.get_id(): item
            for item in book.get_items()
            if item.get_type() == ebooklib.ITEM_DOCUMENT
        }

        lines: list[str] = [
            f"Title: {title}\n",
            f"Author: {author}\n\n",
            "# Title\n",
            f"{title}, by {author}\n\n",
        ]
        for i, sid in enumerate(spine_ids, start=1):
            item = items.get(sid)
            if item is None:
                continue
            chap_title, paragraphs = _chap_to_text(item.get_content())
            if not paragraphs:
                continue
            header = f"# {chap_title}" if chap_title else f"# Part {i}"
            lines.append(f"{header}\n\n")
            for p in paragraphs:
                lines.append(f"{p}\n\n")

        return "".join(lines), title, author

    def parse_txt(self, txt_content: str) -> tuple[list[Chapter], str, str]:
        book_title = "Unknown"
        book_author = "Unknown"
        chapters: list[Chapter] = []
        current_title = "blank"
        current_paragraphs: list[str] = []
        chapter_index = 0
        header_lines = 0
        started = False

        def _flush() -> None:
            nonlocal chapter_index
            if current_paragraphs:
                chapters.append(
                    Chapter(
                        index=chapter_index,
                        title=current_title,
                        paragraphs=list(current_paragraphs),
                    )
                )
                chapter_index += 1

        for raw_line in txt_content.splitlines():
            if header_lines < 2 and (
                raw_line.startswith("Title: ") or raw_line.startswith("Author: ")
            ):
                header_lines += 1
                if raw_line.startswith("Title: "):
                    book_title = raw_line[7:].strip()
                else:
                    book_author = raw_line[8:].strip()
                continue

            line = raw_line.strip()

            if line.startswith("#"):
                if started:
                    _flush()
                    current_paragraphs.clear()
                else:
                    started = True

                raw_title = line[1:].strip()
                current_title = (
                    raw_title if any(c.isalnum() for c in raw_title) else "blank"
                )
            elif line and any(c.isalnum() for c in line):
                if not started:
                    started = True
                    current_title = "blank"

                sentences = sent_tokenize(line)
                cleaned = [s for s in sentences if any(c.isalnum() for c in s)]
                if cleaned:
                    current_paragraphs.append(" ".join(cleaned))

        _flush()
        return chapters, book_title, book_author
