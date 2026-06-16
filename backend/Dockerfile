# ── Stage 1: builder ───────────────────────────────────────────────────────
# Full uv image to resolve + install deps and compile bytecode.
# Nothing from here except the venv reaches the final image.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Layer 1: resolve and install dependencies only (cached until pyproject.toml changes)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Layer 2: install the project package itself
COPY src/ src/
RUN uv sync --no-dev

# Layer 3: download NLTK tokenizer models into the builder's home dir
RUN uv run python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"


# ── Stage 2: runtime ────────────────────────────────────────────────────────
# Lean Python image — no uv, no build tools.
FROM python:3.11-slim AS runtime

# Static ffmpeg binary — single COPY, no apt, no libllvm15 drama
COPY --from=mwader/static-ffmpeg:latest /ffmpeg  /usr/local/bin/ffmpeg
COPY --from=mwader/static-ffmpeg:latest /ffprobe /usr/local/bin/ffprobe

# Pre-built venv from the builder (all packages + compiled .pyc files)
COPY --from=builder /app/.venv      /app/.venv
# NLTK tokenizer data
COPY --from=builder /root/nltk_data /root/nltk_data
# Application source
COPY --from=builder /app/src        /app/src

WORKDIR /app

# Activate the venv — no uv required at runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY entrypoint-worker.sh ./

EXPOSE 8000
