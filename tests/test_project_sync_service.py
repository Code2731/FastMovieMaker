"""Unit tests for local-folder project sync service."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from src.services.project_sync_service import (
    FileSystemSyncBackend,
    GitSyncBackend,
    ProjectSyncService,
    SyncPolicy,
    SyncResultCode,
)


class _FakeSettings:
    def __init__(self) -> None:
        self.state: dict[str, dict[str, str]] = {}
        self.sync_backend = "filesystem"
        self.sync_root_path: str | None = None
        self.sync_git_repo_path: str | None = None

    def get_project_sync_state(self) -> dict[str, dict[str, str]]:
        return dict(self.state)

    def set_project_sync_state(self, state: dict[str, dict[str, str]]) -> None:
        self.state = dict(state)

    def get_project_sync_backend(self) -> str:
        return self.sync_backend

    def get_project_sync_root_path(self) -> str | None:
        return self.sync_root_path

    def get_project_sync_git_repo_path(self) -> str | None:
        return self.sync_git_repo_path


def _git_available() -> bool:
    proc = subprocess.run(["git", "--version"], capture_output=True, text=True)
    return proc.returncode == 0


def test_sync_push_and_no_changes(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    sync_root = tmp_path / "sync"
    sync_root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    first = svc.sync(local, sync_root)
    assert first.code == SyncResultCode.SUCCESS
    assert first.local_info is not None
    assert first.remote_info is not None
    assert (sync_root / "sample.fmm.json").read_text(encoding="utf-8") == '{"a":1}'

    second = svc.sync(local, sync_root)
    assert second.code == SyncResultCode.NO_CHANGES
    assert second.local_info is not None
    assert second.remote_info is not None


def test_sync_auto_conflicts_when_remote_changed_and_local_unchanged(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"base":1}', encoding="utf-8")
    sync_root = tmp_path / "sync"
    sync_root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    assert svc.sync(local, sync_root).code == SyncResultCode.SUCCESS
    (sync_root / "sample.fmm.json").write_text('{"remote":2}', encoding="utf-8")

    result = svc.sync(local, sync_root)
    assert result.code == SyncResultCode.CONFLICT
    assert result.conflict_reason == "remote_changed_requires_reload"
    assert result.local_info is not None
    assert result.remote_info is not None
    assert local.read_text(encoding="utf-8") == '{"base":1}'


def test_sync_use_remote_applies_remote_when_local_unchanged(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"base":1}', encoding="utf-8")
    sync_root = tmp_path / "sync"
    sync_root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    assert svc.sync(local, sync_root).code == SyncResultCode.SUCCESS
    (sync_root / "sample.fmm.json").write_text('{"remote":2}', encoding="utf-8")

    result = svc.sync(local, sync_root, policy=SyncPolicy.USE_REMOTE)
    assert result.code == SyncResultCode.SUCCESS
    assert result.local_info is not None
    assert result.remote_info is not None
    assert local.read_text(encoding="utf-8") == '{"remote":2}'


def test_sync_push_when_local_changed_and_remote_unchanged(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"base":1}', encoding="utf-8")
    sync_root = tmp_path / "sync"
    sync_root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    assert svc.sync(local, sync_root).code == SyncResultCode.SUCCESS
    local.write_text('{"local":3}', encoding="utf-8")

    result = svc.sync(local, sync_root)
    assert result.code == SyncResultCode.SUCCESS
    assert result.local_info is not None
    assert result.remote_info is not None
    assert (sync_root / "sample.fmm.json").read_text(encoding="utf-8") == '{"local":3}'


def test_sync_conflict_and_manual_resolution(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"base":1}', encoding="utf-8")
    sync_root = tmp_path / "sync"
    sync_root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    assert svc.sync(local, sync_root).code == SyncResultCode.SUCCESS
    local.write_text('{"local":4}', encoding="utf-8")
    (sync_root / "sample.fmm.json").write_text('{"remote":5}', encoding="utf-8")

    conflict = svc.sync(local, sync_root)
    assert conflict.code == SyncResultCode.CONFLICT
    assert conflict.local_info is not None
    assert conflict.remote_info is not None
    assert conflict.conflict_reason == "local_and_remote_changed"

    use_remote = svc.sync(local, sync_root, policy=SyncPolicy.USE_REMOTE)
    assert use_remote.code == SyncResultCode.SUCCESS
    assert use_remote.local_info is not None
    assert use_remote.remote_info is not None
    assert local.read_text(encoding="utf-8") == '{"remote":5}'

    local.write_text('{"local":6}', encoding="utf-8")
    (sync_root / "sample.fmm.json").write_text('{"remote":7}', encoding="utf-8")
    conflict2 = svc.sync(local, sync_root)
    assert conflict2.code == SyncResultCode.CONFLICT
    assert conflict2.local_info is not None
    assert conflict2.remote_info is not None
    use_local = svc.sync(local, sync_root, policy=SyncPolicy.USE_LOCAL)
    assert use_local.code == SyncResultCode.SUCCESS
    assert use_local.local_info is not None
    assert use_local.remote_info is not None
    assert (sync_root / "sample.fmm.json").read_text(encoding="utf-8") == '{"local":6}'


def test_sync_fails_for_missing_project_or_invalid_root(tmp_path: Path) -> None:
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    missing_project = tmp_path / "missing.fmm.json"
    root = tmp_path / "sync"
    root.mkdir()

    missing_result = svc.sync(missing_project, root)
    assert missing_result.code == SyncResultCode.ERROR

    local = tmp_path / "sample.fmm.json"
    local.write_text("{}", encoding="utf-8")
    invalid_root = tmp_path / "not_exists"
    invalid_root_result = svc.sync(local, invalid_root)
    assert invalid_root_result.code == SyncResultCode.ERROR
    assert invalid_root_result.local_info is None


def test_sync_fails_when_backend_config_is_missing(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text("{}", encoding="utf-8")
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    settings.sync_backend = "filesystem"
    settings.sync_root_path = None
    fs_missing = svc.sync(local)
    assert fs_missing.code == SyncResultCode.ERROR
    assert "configured" in fs_missing.message

    settings.sync_backend = "git"
    settings.sync_git_repo_path = None
    git_missing = svc.sync(local)
    assert git_missing.code == SyncResultCode.ERROR
    assert "Git sync repository is not configured." == git_missing.message

    settings.sync_git_repo_path = str(tmp_path / "missing-repo")
    git_unavailable = svc.sync(local)
    assert git_unavailable.code == SyncResultCode.ERROR
    assert "Git sync repository is unavailable." == git_unavailable.message


def test_sync_supports_explicit_filesystem_backend(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    root = tmp_path / "sync"
    root.mkdir()
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]

    result = svc.sync(local, backend=FileSystemSyncBackend(root))
    assert result.code == SyncResultCode.SUCCESS
    assert (root / "sample.fmm.json").is_file()


@pytest.mark.skipif(not _git_available(), reason="git is not available")
def test_sync_uses_git_backend_from_settings(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    repo = tmp_path / "sync_repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)

    settings = _FakeSettings()
    settings.sync_backend = "git"
    settings.sync_git_repo_path = str(repo)
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    monkeypatch.setattr(GitSyncBackend, "prepare_remote_sync", lambda self: None)
    monkeypatch.setattr(GitSyncBackend, "finalize_remote_sync_if_needed", lambda self, file_key: None)

    first = svc.sync(local)
    assert first.code == SyncResultCode.SUCCESS
    assert (repo / ".fmm_sync_store" / "sample.fmm.json").is_file()

    local.write_text('{"a":2}', encoding="utf-8")
    second = svc.sync(local)
    assert second.code == SyncResultCode.SUCCESS


class _StubBackend:
    def __init__(self, remote_payload: bytes | None = None, fail_prepare: bool = False) -> None:
        self.remote_payload = remote_payload
        self.fail_prepare = fail_prepare
        self.prepare_calls = 0
        self.finalize_calls = 0

    def fetch(self, file_key: str) -> bytes | None:
        return self.remote_payload

    def store(self, file_key: str, payload: bytes) -> None:
        self.remote_payload = payload

    def describe(self, file_key: str):  # noqa: ANN001
        if self.remote_payload is None:
            return None
        path = Path("/tmp") / file_key
        return type("Info", (), {
            "path": str(path),
            "size_bytes": len(self.remote_payload),
            "modified_at": "2026-03-10T00:00:00+00:00",
            "sha256": "x" * 64,
        })()

    def prepare_remote_sync(self) -> None:
        self.prepare_calls += 1
        if self.fail_prepare:
            raise RuntimeError("prepare failed")

    def finalize_remote_sync_if_needed(self, file_key: str) -> None:
        self.finalize_calls += 1


def test_sync_calls_prepare_and_finalize_for_push(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    backend = _StubBackend(remote_payload=None)

    result = svc.sync(local, backend=backend)

    assert result.code == SyncResultCode.SUCCESS
    assert backend.prepare_calls == 1
    assert backend.finalize_calls == 1


def test_sync_calls_prepare_but_skips_finalize_on_no_changes(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    backend = _StubBackend(remote_payload=b'{"a":1}')

    result = svc.sync(local, backend=backend)

    assert result.code == SyncResultCode.NO_CHANGES
    assert backend.prepare_calls == 1
    assert backend.finalize_calls == 0


def test_sync_use_remote_skips_finalize(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    base_text = '{"base":1}'
    local.write_text(base_text, encoding="utf-8")
    settings = _FakeSettings()
    settings.state["sample.fmm.json"] = {"last_hash": hashlib.sha256(base_text.encode("utf-8")).hexdigest()}
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    backend = _StubBackend(remote_payload=b'{"remote":2}')

    result = svc.sync(local, backend=backend, policy=SyncPolicy.USE_REMOTE)

    assert result.code == SyncResultCode.SUCCESS
    assert backend.prepare_calls == 1
    assert backend.finalize_calls == 0
    assert local.read_text(encoding="utf-8") == '{"remote":2}'


def test_sync_returns_error_when_prepare_remote_sync_fails(tmp_path: Path) -> None:
    local = tmp_path / "sample.fmm.json"
    local.write_text('{"a":1}', encoding="utf-8")
    settings = _FakeSettings()
    svc = ProjectSyncService(settings=settings)  # type: ignore[arg-type]
    backend = _StubBackend(fail_prepare=True)

    result = svc.sync(local, backend=backend)

    assert result.code == SyncResultCode.ERROR
    assert result.message == "Failed to prepare remote git sync."
