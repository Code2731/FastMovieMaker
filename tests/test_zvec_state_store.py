"""Unit tests for zvec local metadata store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.services.zvec_state_store import ZvecStateStore


def test_store_initializes_schema_and_file(tmp_path: Path) -> None:
    db_path = tmp_path / "state.zvec"
    store = ZvecStateStore(db_path=db_path)

    assert store.available is True
    assert db_path.exists()


def test_recent_files_crud(tmp_path: Path) -> None:
    store = ZvecStateStore(db_path=tmp_path / "state.zvec")
    store.set_recent_files(["/tmp/a.fmm", "/tmp/b.fmm"])
    assert store.get_recent_files() == ["/tmp/a.fmm", "/tmp/b.fmm"]

    store.clear_recent_files()
    assert store.get_recent_files() == []


def test_sync_state_crud(tmp_path: Path) -> None:
    store = ZvecStateStore(db_path=tmp_path / "state.zvec")
    payload = {
        "demo.fmm.json": {
            "last_hash": "hash-1",
            "updated_at": "2026-03-13T00:00:00+00:00",
        }
    }
    store.set_sync_state_map(payload)
    assert store.get_sync_state_map() == payload

    store.set_sync_state_map({})
    assert store.get_sync_state_map() == {}


def test_store_is_unavailable_when_sqlite_connect_fails(monkeypatch, tmp_path: Path) -> None:
    def _boom(_path):  # noqa: ANN001
        raise sqlite3.OperationalError("cannot open db")

    monkeypatch.setattr("src.services.zvec_state_store.sqlite3.connect", _boom)
    store = ZvecStateStore(db_path=tmp_path / "broken.zvec")
    assert store.available is False
    assert "cannot open db" in store.error

    with pytest.raises(RuntimeError):
        store.get_recent_files()
