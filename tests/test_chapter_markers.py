"""Tests for timeline marker → MP4 chapter metadata export."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.timeline_marker import TimelineMarker
from src.services.video_exporter import _write_ffmetadata


# ---------------------------------------------------------------------------
# _write_ffmetadata unit tests
# ---------------------------------------------------------------------------

class TestWriteFFMetadata:
    def test_single_marker_creates_one_chapter(self, tmp_path):
        markers = [TimelineMarker(ms=0, name="Intro")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=10_000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert ";FFMETADATA1" in text
        assert "[CHAPTER]" in text
        assert "TIMEBASE=1/1000" in text
        assert "START=0" in text
        assert "END=10000" in text
        assert "title=Intro" in text

    def test_multiple_markers_create_sequential_chapters(self, tmp_path):
        markers = [
            TimelineMarker(ms=0, name="Opening"),
            TimelineMarker(ms=5000, name="Act I"),
            TimelineMarker(ms=15000, name="Act II"),
        ]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=30_000, dest=dest)
        text = dest.read_text(encoding="utf-8")

        assert text.count("[CHAPTER]") == 3
        assert "START=0" in text
        assert "END=5000" in text
        assert "START=5000" in text
        assert "END=15000" in text
        assert "START=15000" in text
        assert "END=30000" in text

    def test_unnamed_marker_gets_auto_label(self, tmp_path):
        markers = [TimelineMarker(ms=0, name=""), TimelineMarker(ms=5000, name="")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=10_000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert "title=Chapter 1" in text
        assert "title=Chapter 2" in text

    def test_markers_sorted_by_time(self, tmp_path):
        markers = [
            TimelineMarker(ms=5000, name="Second"),
            TimelineMarker(ms=0, name="First"),
        ]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=10_000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        first_pos = text.index("title=First")
        second_pos = text.index("title=Second")
        assert first_pos < second_pos

    def test_start_equals_zero_when_marker_at_zero(self, tmp_path):
        markers = [TimelineMarker(ms=0, name="Start")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=5000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert "START=0\n" in text

    def test_last_chapter_ends_at_total_duration(self, tmp_path):
        markers = [TimelineMarker(ms=1000, name="Mid")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=9999, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert "END=9999" in text

    def test_whitespace_stripped_from_name(self, tmp_path):
        markers = [TimelineMarker(ms=0, name="  Trim me  ")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=5000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert "title=Trim me" in text

    def test_blank_name_after_strip_gets_auto_label(self, tmp_path):
        markers = [TimelineMarker(ms=0, name="   ")]
        dest = tmp_path / "meta.ini"
        _write_ffmetadata(markers, total_duration_ms=5000, dest=dest)
        text = dest.read_text(encoding="utf-8")
        assert "title=Chapter 1" in text


# ---------------------------------------------------------------------------
# ExportWorker: markers forwarded to export_video
# ---------------------------------------------------------------------------

class TestExportWorkerMarkersParam:
    def test_markers_passed_to_export_video(self, tmp_path):
        from unittest.mock import MagicMock, patch
        from src.workers.export_worker import ExportWorker
        from src.models.subtitle import SubtitleTrack

        markers = [TimelineMarker(ms=0, name="Start"), TimelineMarker(ms=5000, name="End")]
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        output_path = tmp_path / "out.mp4"
        track = SubtitleTrack()

        worker = ExportWorker(
            video_path=video_path,
            track=track,
            output_path=output_path,
            markers=markers,
        )
        assert worker._markers == markers

    def test_markers_none_by_default(self, tmp_path):
        from src.workers.export_worker import ExportWorker
        from src.models.subtitle import SubtitleTrack

        worker = ExportWorker(
            video_path=tmp_path / "v.mp4",
            track=SubtitleTrack(),
            output_path=tmp_path / "o.mp4",
        )
        assert worker._markers is None
