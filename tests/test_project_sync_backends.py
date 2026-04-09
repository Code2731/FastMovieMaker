"""Backend contract tests for project sync backends."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.services.project_sync_service import FileSystemSyncBackend, GitSyncBackend


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_available() -> bool:
    proc = subprocess.run(["git", "--version"], capture_output=True, text=True)
    return proc.returncode == 0


def test_filesystem_backend_fetch_store_describe(tmp_path: Path) -> None:
    root = tmp_path / "sync"
    root.mkdir()
    backend = FileSystemSyncBackend(root)

    assert backend.fetch("demo.fmm.json") is None

    payload = b'{"name":"demo"}'
    backend.store("demo.fmm.json", payload)

    fetched = backend.fetch("demo.fmm.json")
    assert fetched == payload

    info = backend.describe("demo.fmm.json")
    assert info is not None
    assert info.path.endswith("demo.fmm.json")
    assert info.size_bytes == len(payload)
    assert len(info.sha256) == 64


@pytest.mark.skipif(not _git_available(), reason="git is not available")
def test_git_backend_fetch_store_describe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)

    backend = GitSyncBackend(repo)
    payload = b'{"id":1}'
    backend.store("demo.fmm.json", payload)

    fetched = backend.fetch("demo.fmm.json")
    assert fetched == payload

    info = backend.describe("demo.fmm.json")
    assert info is not None
    assert info.path.endswith(".fmm_sync_store/demo.fmm.json")
    assert info.size_bytes == len(payload)


@pytest.mark.skipif(not _git_available(), reason="git is not available")
def test_git_backend_raises_when_repo_invalid(tmp_path: Path) -> None:
    missing_repo = tmp_path / "missing-repo"
    backend = GitSyncBackend(missing_repo)

    with pytest.raises(RuntimeError, match="Git sync repository is unavailable\\."):
        backend.fetch("demo.fmm.json")

    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    invalid_backend = GitSyncBackend(repo)
    with pytest.raises(RuntimeError, match="Git sync repository is invalid\\."):
        invalid_backend.fetch("demo.fmm.json")


def test_git_backend_stage_error_is_standardized(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args[:3] == ["status", "--porcelain", "--"]:
            return _Result(0, stdout=" M .fmm_sync_store/demo.fmm.json")
        if args[:2] == ["add", "--"]:
            return _Result(1, stderr="add failed")
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Failed to stage sync file in git repository\\."):
        backend.finalize_remote_sync_if_needed("demo.fmm.json")


def test_git_backend_prepare_blocks_dirty_repo(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args == ["status", "--porcelain"]:
            return _Result(0, stdout=" M dirty.txt")
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Git sync requires a clean working tree\\."):
        backend.prepare_remote_sync()


def test_git_backend_prepare_blocks_without_upstream(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args == ["status", "--porcelain"]:
            return _Result(0)
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Result(1)
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Git upstream is not configured for current branch\\."):
        backend.prepare_remote_sync()


def test_git_backend_prepare_blocks_when_origin_missing(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args == ["status", "--porcelain"]:
            return _Result(0)
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Result(0, stdout="origin/main")
        if args == ["remote", "get-url", "origin"]:
            return _Result(1)
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Git remote 'origin' is not configured\\."):
        backend.prepare_remote_sync()


def test_git_backend_prepare_blocks_when_pull_ff_only_fails(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args == ["status", "--porcelain"]:
            return _Result(0)
        if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Result(0, stdout="origin/main")
        if args == ["remote", "get-url", "origin"]:
            return _Result(0, stdout="https://example.com/repo.git")
        if args == ["fetch", "origin", "main"]:
            return _Result(0)
        if args == ["pull", "--ff-only", "origin", "main"]:
            return _Result(1, stderr="not possible to fast-forward")
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Failed to pull from origin with ff-only policy\\."):
        backend.prepare_remote_sync()


def test_git_backend_finalize_skips_when_sync_file_unchanged(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")
    calls: list[list[str]] = []

    def _fake_run_git(args: list[str]) -> _Result:
        calls.append(args)
        if args[:3] == ["status", "--porcelain", "--"]:
            return _Result(0, stdout="")
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    backend.finalize_remote_sync_if_needed("demo.fmm.json")

    assert calls == [["status", "--porcelain", "--", ".fmm_sync_store/demo.fmm.json"]]


def test_git_backend_finalize_push_failure_is_standardized(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = GitSyncBackend(repo)
    monkeypatch.setattr(backend, "_validate_repo", lambda: None)
    monkeypatch.setattr(backend, "_current_branch", lambda: "main")

    def _fake_run_git(args: list[str]) -> _Result:
        if args[:3] == ["status", "--porcelain", "--"]:
            return _Result(0, stdout=" M .fmm_sync_store/demo.fmm.json")
        if args[:2] == ["add", "--"]:
            return _Result(0)
        if args[:2] == ["commit", "-m"]:
            return _Result(0, stdout="[main abc123] sync")
        if args == ["push", "origin", "main"]:
            return _Result(1, stderr="push failed")
        return _Result(0)

    monkeypatch.setattr(backend, "_run_git", _fake_run_git)

    with pytest.raises(RuntimeError, match="Failed to push sync commit to origin\\."):
        backend.finalize_remote_sync_if_needed("demo.fmm.json")
