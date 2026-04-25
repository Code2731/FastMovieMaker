"""Shared pytest test-time configuration."""

from __future__ import annotations

import gc
import os
import sys

import pytest

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
