"""Automatic project sync manager — periodic background sync via QTimer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from src.services.project_sync_service import ProjectSyncService, SyncPolicy, SyncResultCode
from src.services.settings_manager import SettingsManager

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

_MIN_INTERVAL_MINUTES = 1
_MAX_INTERVAL_MINUTES = 60
_DEFAULT_INTERVAL_MINUTES = 5


class AutoSyncManager(QObject):
    """Periodically syncs the current project using AUTO policy.

    Conflicts are not surfaced as dialogs — the sync is silently skipped
    and reported via the ``sync_message`` signal so the caller can show
    it in the status bar without blocking the user.
    """

    sync_message = Signal(str, int)  # (message, timeout_ms); 0 = persistent

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = SettingsManager()
        self._project_path: Path | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._apply_settings()

    # ------------------------------------------------------------------ public

    def set_project_path(self, path: Path | None) -> None:
        """Notify the manager of the current project file path."""
        self._project_path = path

    def apply_settings(self) -> None:
        """Re-read settings and restart/stop the timer accordingly."""
        self._apply_settings()

    # ----------------------------------------------------------------- private

    def _apply_settings(self) -> None:
        enabled = self._settings.get_project_sync_auto_enabled()
        interval_min = self._settings.get_project_sync_auto_interval_minutes()
        interval_min = max(_MIN_INTERVAL_MINUTES, min(_MAX_INTERVAL_MINUTES, interval_min))

        if enabled:
            self._timer.start(interval_min * 60 * 1000)
        else:
            self._timer.stop()

    @Slot()
    def _on_timer(self) -> None:
        path = self._project_path
        if path is None or not path.is_file():
            return

        sync_root = self._settings.get_project_sync_root_path()
        sync_backend = self._settings.get_project_sync_backend()
        if not sync_root and sync_backend == "filesystem":
            return
        git_repo = self._settings.get_project_sync_git_repo_path()
        if not git_repo and sync_backend == "git":
            return

        try:
            service = ProjectSyncService(settings=self._settings)
            result = service.sync(path, policy=SyncPolicy.AUTO)
        except Exception as exc:
            _LOGGER.warning("Auto sync failed: %s", exc)
            self.sync_message.emit(f"Auto sync error: {exc}", 4000)
            return

        if result.code == SyncResultCode.SUCCESS:
            self.sync_message.emit("Auto sync completed.", 3000)
        elif result.code == SyncResultCode.NO_CHANGES:
            pass  # Silently ignore — nothing changed
        elif result.code == SyncResultCode.CONFLICT:
            # Don't interrupt the user with a dialog during auto sync.
            _LOGGER.info("Auto sync skipped: conflict detected for %s", path.name)
            self.sync_message.emit(
                f"Auto sync: conflict on '{path.name}' — use Sync Now to resolve.", 5000
            )
        else:
            _LOGGER.warning("Auto sync error: %s — %s", result.code, result.message)
            self.sync_message.emit(f"Auto sync failed: {result.message}", 4000)
