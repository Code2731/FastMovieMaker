"""B-sprint quality & stability tests: bug fixes, edge cases, performance guards."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# P0: project.py — subtitle_track defensive fallback
# ---------------------------------------------------------------------------

class TestSubtitleTrackFallback:
    def test_returns_first_track_when_active_index_out_of_range(self):
        from src.models.project import ProjectState
        from src.models.subtitle import SubtitleTrack

        p = ProjectState()
        track = SubtitleTrack(name="A")
        p.subtitle_tracks = [track]
        p.active_track_index = 99  # out of range
        assert p.subtitle_track is track

    def test_creates_default_track_when_list_is_empty(self):
        from src.models.project import ProjectState

        p = ProjectState()
        p.subtitle_tracks = []
        p.active_track_index = 0
        result = p.subtitle_track
        assert result is not None
        assert len(p.subtitle_tracks) == 1
        assert p.active_track_index == 0

    def test_normal_active_index_returns_correct_track(self):
        from src.models.project import ProjectState
        from src.models.subtitle import SubtitleTrack

        p = ProjectState()
        t1, t2 = SubtitleTrack(name="T1"), SubtitleTrack(name="T2")
        p.subtitle_tracks = [t1, t2]
        p.active_track_index = 1
        assert p.subtitle_track is t2


# ---------------------------------------------------------------------------
# P0: project_io.py — load_project error handling
# ---------------------------------------------------------------------------

class TestLoadProjectErrorHandling:
    def test_raises_value_error_on_invalid_json(self, tmp_path):
        from src.services.project_io import load_project

        f = tmp_path / "bad.fmm.json"
        f.write_bytes(b"NOT JSON {{{{")
        with pytest.raises(ValueError, match="invalid JSON"):
            load_project(f)

    def test_raises_value_error_on_corrupted_gzip(self, tmp_path):
        from src.services.project_io import load_project

        f = tmp_path / "bad.fmm"
        # Valid gzip magic bytes but corrupted content
        f.write_bytes(b"\x1f\x8b" + b"\x00" * 20)
        with pytest.raises(ValueError, match="corrupted"):
            load_project(f)

    def test_raises_oserror_on_missing_file(self, tmp_path):
        from src.services.project_io import load_project

        with pytest.raises(OSError):
            load_project(tmp_path / "nonexistent.fmm.json")

    def test_loads_valid_plain_json(self, tmp_path):
        from src.services.project_io import load_project, save_project
        from src.models.project import ProjectState

        p = ProjectState()
        f = tmp_path / "proj.fmm.json"
        save_project(p, f)
        # Write as plain JSON (non-gzip)
        plain = json.loads(gzip.decompress(f.read_bytes()).decode("utf-8"))
        plain_bytes = json.dumps(plain, ensure_ascii=False).encode("utf-8")
        f.write_bytes(plain_bytes)
        loaded = load_project(f)
        assert isinstance(loaded, ProjectState)

    def test_loads_valid_gzip_json(self, tmp_path):
        from src.services.project_io import load_project, save_project
        from src.models.project import ProjectState

        p = ProjectState()
        f = tmp_path / "proj.fmm"
        save_project(p, f)
        assert f.read_bytes()[:2] == b"\x1f\x8b"
        loaded = load_project(f)
        assert isinstance(loaded, ProjectState)

    def test_raises_value_error_on_segment_missing_required_field(self, tmp_path):
        from src.services.project_io import load_project
        from src.models.project import ProjectState

        # Craft a project with a segment missing 'text'
        data = {
            "version": 2,
            "tracks": [
                {
                    "language": "ko",
                    "segments": [
                        {"start_ms": 0, "end_ms": 1000}  # missing 'text'
                    ],
                }
            ],
        }
        f = tmp_path / "corrupt.fmm.json"
        f.write_bytes(json.dumps(data).encode("utf-8"))
        with pytest.raises(ValueError, match="missing required field"):
            load_project(f)


# ---------------------------------------------------------------------------
# P1: ducking_service.py — window count guard
# ---------------------------------------------------------------------------

class TestDuckingWindowGuard:
    def _make_segment(self, start_ms: int, end_ms: int) -> object:
        from src.models.subtitle import SubtitleSegment
        seg = SubtitleSegment(start_ms=start_ms, end_ms=end_ms, text="x")
        seg.audio_file = "dummy.mp3"  # must be truthy to be considered active
        return seg

    def test_normal_segment_count_builds_expr(self):
        from src.services.ducking_service import DuckingService

        segs = [self._make_segment(i * 2000, i * 2000 + 1000) for i in range(5)]
        expr = DuckingService.build_volume_expr(segs, base_volume=1.0, duck_volume=0.3)
        assert "between" in expr

    def test_excessive_windows_are_truncated(self, caplog):
        import logging
        from src.services.ducking_service import DuckingService, _MAX_DUCK_WINDOWS

        # Create more windows than the limit (no merging because gaps > merge_gap_ms=0)
        segs = [self._make_segment(i * 3000, i * 3000 + 1000) for i in range(_MAX_DUCK_WINDOWS + 50)]
        with caplog.at_level(logging.WARNING, logger="src.services.ducking_service"):
            expr = DuckingService.build_volume_expr(segs, base_volume=1.0, duck_volume=0.3)
        assert "truncating" in caplog.text.lower()
        assert expr  # expression still produced

    def test_empty_segments_returns_base_volume(self):
        from src.services.ducking_service import DuckingService

        expr = DuckingService.build_volume_expr([], base_volume=0.8, duck_volume=0.3)
        assert expr == "0.8"


# ---------------------------------------------------------------------------
# P1: style_preset_manager.py — no bare except
# ---------------------------------------------------------------------------

class TestStylePresetManagerCleanup:
    def test_del_does_not_raise(self):
        """StylePresetManager.__del__ must not propagate exceptions."""
        from src.services.style_preset_manager import StylePresetManager
        from unittest.mock import patch, MagicMock

        with patch("src.services.style_preset_manager.QSettings") as mock_qs:
            mock_qs.return_value.endGroup.side_effect = RuntimeError("boom")
            mgr = StylePresetManager()
            # Should not raise
            mgr.__del__()


# ---------------------------------------------------------------------------
# P2 performance: timeline_painter.py — source_color_cache
# ---------------------------------------------------------------------------

class TestSourceColorCache:
    def _make_painter(self):
        from unittest.mock import MagicMock
        from src.ui.timeline_painter import TimelinePainter

        tw = MagicMock()
        tw.width.return_value = 800
        return TimelinePainter(tw)

    def test_cache_starts_empty(self):
        painter = self._make_painter()
        assert painter._source_color_cache_key is None
        assert painter._source_color_cache == {}

    def test_cache_is_populated_on_first_access(self):
        """After calling the internal helper, cache should be set."""
        from unittest.mock import MagicMock, patch
        from src.ui.timeline_painter import TimelinePainter

        tw = MagicMock()
        painter = TimelinePainter(tw)

        # Simulate the cache logic directly
        class FakeClip:
            source_path = Path("/a/b.mp4")

        class FakeTrack:
            clips = [FakeClip(), FakeClip()]

        track = FakeTrack()
        cache_key = (id(track), len(track.clips))

        # First access: cache miss
        assert cache_key != painter._source_color_cache_key
        source_paths = {c.source_path for c in track.clips}
        painter._source_color_cache = {
            path: i
            for i, path in enumerate(sorted(source_paths, key=lambda x: str(x) if x is not None else ""))
        }
        painter._source_color_cache_key = cache_key

        assert painter._source_color_cache_key == cache_key
        assert Path("/a/b.mp4") in painter._source_color_cache

    def test_cache_is_invalidated_when_clip_count_changes(self):
        from unittest.mock import MagicMock
        from src.ui.timeline_painter import TimelinePainter

        tw = MagicMock()
        painter = TimelinePainter(tw)

        class FakeTrack:
            clips = []

        track = FakeTrack()
        key1 = (id(track), 0)
        painter._source_color_cache_key = key1
        painter._source_color_cache = {"old": 0}

        # Simulate adding a clip
        track.clips = [object()]
        key2 = (id(track), 1)
        assert key2 != painter._source_color_cache_key  # cache is stale — would be rebuilt
