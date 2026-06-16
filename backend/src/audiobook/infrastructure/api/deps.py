"""
Dependency injection — wires infrastructure adapters to ports.
FastAPI routes call these factories to get concrete implementations.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings

from ..adapters.audio_merger import PydubAudioMerger
from ..adapters.epub_reader import EbooklibEpubReader
from ..adapters.redis_store import RedisJobStore, RedisProgressBus
from ..adapters.tts_engine import EdgeTTSEngine


class Settings(BaseSettings):
    api_key: str = "changeme"
    redis_url: str = "redis://localhost:6379/0"
    output_dir: str = "/app/output"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_job_store() -> RedisJobStore:
    return RedisJobStore(get_settings().redis_url)


def get_progress_bus() -> RedisProgressBus:
    return RedisProgressBus(get_settings().redis_url)


def get_epub_reader() -> EbooklibEpubReader:
    return EbooklibEpubReader()


def get_tts_engine() -> EdgeTTSEngine:
    return EdgeTTSEngine()
