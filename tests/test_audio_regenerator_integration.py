"""Integration tests for AudioRegenerator with segment settings."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.subtitle import SubtitleSegment, SubtitleTrack
from src.services.audio_regenerator import AudioRegenerator


class TestAudioRegeneratorIntegration:
    """Test AudioRegenerator integration with segment settings."""

    @pytest.fixture
    def mock_ffmpeg_runner(self):
        """Mock FFmpeg runner and create dummy output files so copy2(tts_audio, output_path) succeeds."""
        def run_side_effect(args, check=False):
            # Create any .mp3 output file that FFmpeg would have created (last path in args)
            for a in args:
                if isinstance(a, str) and a.endswith(".mp3"):
                    p = Path(a)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(b"\x00\x00")  # minimal dummy
            return MagicMock(returncode=0)

        with patch("src.services.audio_regenerator.get_ffmpeg_runner") as mock_get:
            runner = MagicMock()
            runner.is_available.return_value = True
            runner.run.side_effect = run_side_effect
            mock_get.return_value = runner
            yield runner

    def test_regenerate_track_audio_applies_segment_volume(self, mock_ffmpeg_runner, tmp_path):
        """Test that regenerate_track_audio applies per-segment volume settings."""
        # Setup track with segments having different volumes
        track = SubtitleTrack()
        
        # Create dummy audio files
        audio1 = tmp_path / "seg1.mp3"
        audio1.write_text("dummy audio content 1")
        
        audio2 = tmp_path / "seg2.mp3"
        audio2.write_text("dummy audio content 2")
        
        # Segment 1: Volume 1.5 (should trigger volume filter)
        seg1 = SubtitleSegment(0, 1000, "Segment 1", audio_file=str(audio1), volume=1.5)
        track.add_segment(seg1)
        
        # Segment 2: Volume 1.0 (should NOT trigger volume filter)
        seg2 = SubtitleSegment(1000, 2000, "Segment 2", audio_file=str(audio2), volume=1.0)
        track.add_segment(seg2)
        
        output_path = tmp_path / "output.mp3"
        
        # Run regeneration
        AudioRegenerator.regenerate_track_audio(
            track=track,
            output_path=output_path,
            apply_segment_volumes=True
        )
        
        # Verify FFmpeg calls
        # We expect calls to create silence, apply volume, and concat
        
        # Check for volume filter call for segment 1
        volume_filter_called = False
        for call in mock_ffmpeg_runner.run.call_args_list:
            args = call[0][0]
            # Check if this call is applying volume filter
            if "-af" in args and "volume=1.50" in args[args.index("-af") + 1]:
                volume_filter_called = True
                # Verify input file is correct
                assert str(audio1) in args
                
        assert volume_filter_called, "FFmpeg volume filter was not called for segment with volume 1.5"
        
        # Check that NO volume filter was called for segment 2 (volume 1.0)
        volume_1_0_called = False
        for call in mock_ffmpeg_runner.run.call_args_list:
            args = call[0][0]
            if "-af" in args and "volume=1.00" in args[args.index("-af") + 1]:
                volume_1_0_called = True
                
        assert not volume_1_0_called, "FFmpeg volume filter should not be called for volume 1.0"

    @patch("src.services.audio_merger.AudioMerger.mix_audio_tracks")
    @patch("src.services.ducking_service.DuckingService.build_volume_expr")
    def test_regenerate_track_audio_passes_ducking_smoothing_params(
        self,
        mock_build_expr,
        mock_mix_audio_tracks,
        mock_ffmpeg_runner,
        tmp_path,
    ):
        """Ducking enabled path should forward attack/release/merge parameters."""
        track = SubtitleTrack()
        audio1 = tmp_path / "seg1.mp3"
        audio1.write_text("dummy audio content 1", encoding="utf-8")
        seg1 = SubtitleSegment(0, 1000, "Segment 1", audio_file=str(audio1), volume=1.0)
        track.add_segment(seg1)

        mock_build_expr.return_value = "if(gt(between(t,0.000,1.000),0),0.300,0.800)"
        output_path = tmp_path / "output_duck.mp3"
        bg_audio = tmp_path / "bg.mp3"
        bg_audio.write_text("bg", encoding="utf-8")

        AudioRegenerator.regenerate_track_audio(
            track=track,
            output_path=output_path,
            video_audio_path=bg_audio,
            ducking_enabled=True,
            duck_level=0.3,
            duck_attack_ms=120,
            duck_release_ms=240,
            duck_merge_gap_ms=150,
        )

        mock_build_expr.assert_called_once()
        build_kwargs = mock_build_expr.call_args.kwargs
        assert build_kwargs["attack_ms"] == 120
        assert build_kwargs["release_ms"] == 240
        assert build_kwargs["merge_gap_ms"] == 150

        mock_mix_audio_tracks.assert_called_once()
        mix_kwargs = mock_mix_audio_tracks.call_args.kwargs
        assert mix_kwargs["track1_volume"] == mock_build_expr.return_value

    @patch("src.services.audio_merger.AudioMerger.mix_audio_tracks")
    @patch("src.services.ducking_service.DuckingService.build_volume_expr")
    def test_regenerate_track_audio_skips_smoothing_when_ducking_disabled(
        self,
        mock_build_expr,
        mock_mix_audio_tracks,
        mock_ffmpeg_runner,
        tmp_path,
    ):
        """Ducking disabled path should keep plain background volume."""
        track = SubtitleTrack()
        audio1 = tmp_path / "seg1.mp3"
        audio1.write_text("dummy audio content 1", encoding="utf-8")
        seg1 = SubtitleSegment(0, 1000, "Segment 1", audio_file=str(audio1), volume=1.0)
        track.add_segment(seg1)

        output_path = tmp_path / "output_plain.mp3"
        bg_audio = tmp_path / "bg.mp3"
        bg_audio.write_text("bg", encoding="utf-8")

        AudioRegenerator.regenerate_track_audio(
            track=track,
            output_path=output_path,
            video_audio_path=bg_audio,
            bg_volume=0.6,
            ducking_enabled=False,
        )

        mock_build_expr.assert_not_called()
        mock_mix_audio_tracks.assert_called_once()
        mix_kwargs = mock_mix_audio_tracks.call_args.kwargs
        assert mix_kwargs["track1_volume"] == 0.6
