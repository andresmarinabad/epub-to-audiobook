"""FastAPI application entry point."""
import os
import time

import nltk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from ..logging import configure_logging, get_logger
from .routes import epub, jobs, voices

configure_logging()
log = get_logger(__name__)

# Download NLTK data at startup if missing (idempotent)
_NLTK_DATA = os.environ.get("NLTK_DATA", os.path.expanduser("~/nltk_data"))
for _corpus in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{_corpus}")
    except LookupError:
        nltk.download(_corpus, download_dir=_NLTK_DATA, quiet=True)


app = FastAPI(
    title="epub2audiobook API",
    description="Convert EPUB files to chaptered M4B audiobooks using Edge TTS",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # nginx is the public face; CORS can be locked down per env
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(epub.router)
app.include_router(jobs.router)
app.include_router(voices.router)


@app.middleware("http")
async def _access_log(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    log.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round((time.monotonic() - t0) * 1000),
    )
    return response


@app.get("/api/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
