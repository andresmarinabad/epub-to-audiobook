"""Shared pytest fixtures."""
from __future__ import annotations

import nltk
import pytest
from fastapi.testclient import TestClient

from audiobook.infrastructure.api.deps import Settings, get_settings
from audiobook.infrastructure.api.main import app

# Ensure NLTK tokenizer data is present before any test runs
for _corpus in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{_corpus}")
    except LookupError:
        nltk.download(_corpus, quiet=True)

TEST_SETTINGS = Settings(
    api_key="test-key",
    redis_url="redis://localhost:6379/0",
    output_dir="/tmp/test-audiobook-output",
)
API_HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture
def client():
    """FastAPI test client with settings overridden to avoid real Redis/disk deps."""
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()
