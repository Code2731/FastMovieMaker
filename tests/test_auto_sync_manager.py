"""Unit tests for AutoSyncManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.auto_sync_manager import AutoSyncManager
from src.services.project_sync_service import SyncResult, SyncResultCode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(
    enabled: bool = False,
    interval: int = 5,
    backend: str = "filesystem",
    root: str | None = "/tmp/sync",
    git_repo: str | None = None,
) -> MagicMock:
    s = MagicMock()
    s.get_project_sync_auto_enabled.return_value = enabled
    s.get_project_sync_auto_interval_minutes.return_value = interval
    s.get_project_sync_backend.return_value = backend
    s.get_project_sync_root_path.return_value = root
    s.get_project_sync_git_repo_path.return_value = git_repo
    return s


def _make_result(code: SyncResultCode, message: str = "", detail: str = "") -> SyncResult:
    return SyncResult(code=code, message=message, file_key="test", detail=detail)


# ---------------------------------------------------------------------------
# Settings applied on construction
# ---------------------------------------------------------------------------

class TestAutoSyncManagerInit:
    def test_timer_stopped_when_disabled(self, qtbot):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=_make_settings(enabled=False)):
            mgr = AutoSyncManager()
            assert not mgr._timer.isActive()

    def test_timer_started_when_enabled(self, qtbot):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=_make_settings(enabled=True, interval=1)):
            mgr = AutoSyncManager()
            assert mgr._timer.isActive()
            assert mgr._timer.interval() == 60_000  # 1 minute

    def test_interval_clamped_to_minimum(self, qtbot):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=_make_settings(enabled=True, interval=0)):
            mgr = AutoSyncManager()
            assert mgr._timer.interval() == 60_000  # min 1 minute

    def test_interval_clamped_to_maximum(self, qtbot):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=_make_settings(enabled=True, interval=999)):
            mgr = AutoSyncManager()
            assert mgr._timer.interval() == 60 * 60_000  # max 60 minutes


# ---------------------------------------------------------------------------
# set_project_path
# ---------------------------------------------------------------------------

class TestSetProjectPath:
    def test_set_and_clear(self, qtbot, tmp_path):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=_make_settings()):
            mgr = AutoSyncManager()
            p = tmp_path / "project.fmm"
            p.touch()
            mgr.set_project_path(p)
            assert mgr._project_path == p
            mgr.set_project_path(None)
            assert mgr._project_path is None


# ---------------------------------------------------------------------------
# apply_settings (re-read after preferences change)
# ---------------------------------------------------------------------------

class TestApplySettings:
    def test_starts_timer_when_now_enabled(self, qtbot):
        settings = _make_settings(enabled=False)
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=settings):
            mgr = AutoSyncManager()
            assert not mgr._timer.isActive()

        settings.get_project_sync_auto_enabled.return_value = True
        settings.get_project_sync_auto_interval_minutes.return_value = 5
        mgr._settings = settings
        mgr.apply_settings()
        assert mgr._timer.isActive()

    def test_stops_timer_when_disabled(self, qtbot):
        settings = _make_settings(enabled=True, interval=1)
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=settings):
            mgr = AutoSyncManager()
            assert mgr._timer.isActive()

        settings.get_project_sync_auto_enabled.return_value = False
        mgr._settings = settings
        mgr.apply_settings()
        assert not mgr._timer.isActive()


# ---------------------------------------------------------------------------
# _on_timer: sync trigger logic
# ---------------------------------------------------------------------------

class TestOnTimer:
    def _mgr(self, qtbot, settings):
        with patch("src.services.auto_sync_manager.SettingsManager", return_value=settings):
            mgr = AutoSyncManager()
            mgr._settings = settings
            return mgr

    def test_skips_when_no_project_path(self, qtbot):
        settings = _make_settings()
        mgr = self._mgr(qtbot, settings)
        mgr.set_project_path(None)
        with patch("src.services.auto_sync_manager.ProjectSyncService") as svc_cls:
            mgr._on_timer()
            svc_cls.assert_not_called()

    def test_skips_when_file_missing(self, qtbot, tmp_path):
        settings = _make_settings()
        mgr = self._mgr(qtbot, settings)
        mgr.set_project_path(tmp_path / "missing.fmm")
        with patch("src.services.auto_sync_manager.ProjectSyncService") as svc_cls:
            mgr._on_timer()
            svc_cls.assert_not_called()

    def test_skips_when_filesystem_root_not_set(self, qtbot, tmp_path):
        settings = _make_settings(backend="filesystem", root=None)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)
        with patch("src.services.auto_sync_manager.ProjectSyncService") as svc_cls:
            mgr._on_timer()
            svc_cls.assert_not_called()

    def test_skips_when_git_repo_not_set(self, qtbot, tmp_path):
        settings = _make_settings(backend="git", root=None, git_repo=None)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)
        with patch("src.services.auto_sync_manager.ProjectSyncService") as svc_cls:
            mgr._on_timer()
            svc_cls.assert_not_called()

    def test_emits_message_on_success(self, qtbot, tmp_path):
        settings = _make_settings(enabled=True)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)

        svc_mock = MagicMock()
        svc_mock.sync.return_value = _make_result(SyncResultCode.SUCCESS)
        with patch("src.services.auto_sync_manager.ProjectSyncService", return_value=svc_mock):
            messages = []
            mgr.sync_message.connect(lambda m, t: messages.append(m))
            mgr._on_timer()
            assert any("completed" in m for m in messages)

    def test_silent_on_no_changes(self, qtbot, tmp_path):
        settings = _make_settings(enabled=True)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)

        svc_mock = MagicMock()
        svc_mock.sync.return_value = _make_result(SyncResultCode.NO_CHANGES)
        with patch("src.services.auto_sync_manager.ProjectSyncService", return_value=svc_mock):
            messages = []
            mgr.sync_message.connect(lambda m, t: messages.append(m))
            mgr._on_timer()
            assert not messages  # No message for NO_CHANGES

    def test_emits_conflict_notice_without_dialog(self, qtbot, tmp_path):
        settings = _make_settings(enabled=True)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)

        svc_mock = MagicMock()
        svc_mock.sync.return_value = _make_result(SyncResultCode.CONFLICT)
        with patch("src.services.auto_sync_manager.ProjectSyncService", return_value=svc_mock):
            messages = []
            mgr.sync_message.connect(lambda m, t: messages.append(m))
            mgr._on_timer()
            assert any("conflict" in m.lower() for m in messages)

    def test_emits_error_message_on_sync_exception(self, qtbot, tmp_path):
        settings = _make_settings(enabled=True)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)

        svc_mock = MagicMock()
        svc_mock.sync.side_effect = RuntimeError("network failure")
        with patch("src.services.auto_sync_manager.ProjectSyncService", return_value=svc_mock):
            messages = []
            mgr.sync_message.connect(lambda m, t: messages.append(m))
            mgr._on_timer()
            assert any("error" in m.lower() for m in messages)

    def test_emits_error_on_error_result(self, qtbot, tmp_path):
        settings = _make_settings(enabled=True)
        mgr = self._mgr(qtbot, settings)
        p = tmp_path / "proj.fmm"
        p.touch()
        mgr.set_project_path(p)

        svc_mock = MagicMock()
        svc_mock.sync.return_value = _make_result(SyncResultCode.ERROR, message="disk full")
        with patch("src.services.auto_sync_manager.ProjectSyncService", return_value=svc_mock):
            messages = []
            mgr.sync_message.connect(lambda m, t: messages.append(m))
            mgr._on_timer()
            assert any("failed" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# SettingsManager integration (real SettingsManager, no mock)
# ---------------------------------------------------------------------------

class TestSettingsManagerIntegration:
    def test_new_settings_defaults(self):
        from src.services.settings_manager import SettingsManager
        from unittest.mock import patch as p2

        with p2("src.services.settings_manager.QSettings") as mock_qs:
            mock_qs.return_value.value.side_effect = lambda key, default, *a: default
            mock_qs.return_value.sync = MagicMock()
            with p2("src.services.settings_manager.ZvecStateStore") as mock_zs:
                mock_zs.return_value.available = False
                sm = SettingsManager()
                assert sm.get_project_sync_auto_enabled() is False
                assert sm.get_project_sync_auto_interval_minutes() == 5
