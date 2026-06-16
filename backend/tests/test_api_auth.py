"""Tests for API authentication middleware."""
from __future__ import annotations

import pytest


def test_epub_parse_without_key_returns_403(client):
    res = client.post("/api/epub/parse")
    assert res.status_code == 403


def test_epub_parse_with_wrong_key_returns_403(client):
    res = client.post("/api/epub/parse", headers={"X-API-Key": "wrong"})
    assert res.status_code == 403


def test_get_job_without_key_returns_403(client):
    res = client.get("/api/jobs/any-id")
    assert res.status_code == 403


def test_get_job_with_wrong_key_returns_403(client):
    res = client.get("/api/jobs/any-id", headers={"X-API-Key": "bad"})
    assert res.status_code == 403


def test_start_job_without_key_returns_403(client):
    res = client.post("/api/jobs", json={})
    assert res.status_code == 403


def test_voices_without_key_returns_403(client):
    res = client.get("/api/voices")
    assert res.status_code == 403


def test_valid_key_passes_auth_layer(client):
    # A 404 (not 403) means auth passed and we hit the actual handler
    res = client.get("/api/jobs/nonexistent", headers={"X-API-Key": "test-key"})
    assert res.status_code != 403
