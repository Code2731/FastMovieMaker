"""Shared pytest test-time configuration."""

from __future__ import annotations

import gc
import os
import sys

import pytest

# MS Store Python(WindowsApps) 샌드박스에서 심볼릭링크 resolve() 시 WinError 448 발생.
# tmpdir.py가 cleanup_dead_symlinks를 직접 import하므로 두 모듈 모두 패치한다.
try:
    from _pytest import pathlib as _pytest_pathlib
    from _pytest import tmpdir as _pytest_tmpdir

    _orig_cleanup = _pytest_pathlib.cleanup_dead_symlinks

    def _safe_cleanup_dead_symlinks(root):
        try:
            _orig_cleanup(root)
        except OSError:
            pass

    _pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
    _pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
except Exception:
    pass

# Keep Qt tests headless/stable on macOS CI and local CLI runs.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp_session():
    """세션 전체에서 QApplication 인스턴스를 유지해 GC 세그폴트를 방지한다."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app
    app.processEvents()
    gc.collect()


@pytest.fixture(autouse=True)
def _keep_qapp(qapp_session):
    """모든 테스트에 qapp_session을 자동으로 주입한다."""
    yield
