"""Background worker for batch video export."""

from __future__ import annotations

import shutil
import tempfile
import uuid
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.models.export_preset import BatchExportJob
from src.models.subtitle import SubtitleTrack
from src.services.video_exporter import export_video

_LOGGER = logging.getLogger(__name__)


class BatchExportWorker(QObject):
    """Runs multiple export jobs sequentially in a background thread."""

    job_started = Signal(int, str)
    job_progress = Signal(int, float, float)
    job_finished = Signal(int, str)
    job_error = Signal(int, str)
    all_finished = Signal(int, int, int)

    def __init__(
        self,
        video_path: Path,
        track: SubtitleTrack,
        jobs: list[BatchExportJob],
        audio_path: Path | None = None,
        overlay_path: Path | None = None,
        image_overlays: list | None = None,
        text_overlays: list | None = None,
        mix_with_original_audio: bool = False,
        video_volume: float = 1.0,
        audio_volume: float = 1.0,
        apply_segment_volumes: bool = True,
    ):
        super().__init__()
        self._video_path = video_path
        self._track = track
        self._jobs = jobs
        self._audio_path = audio_path
        self._overlay_path = overlay_path
        self._image_overlays = image_overlays
        self._text_overlays = text_overlays
        self._mix_with_original_audio = mix_with_original_audio
        self._video_volume = video_volume
        self._audio_volume = audio_volume
        self._apply_segment_volumes = apply_segment_volumes
        self._cancelled = False
        self._temp_dirs: list[Path] = []

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        succeeded = 0
        failed = 0

        # Track-to-audio cache to avoid regenerating the same track audio multiple times
        track_audio_cache: dict[int, Path] = {}

        for i, job in enumerate(self._jobs):
            if self._cancelled:
                job.status = "skipped"
                continue

            job.status = "running"
            self.job_started.emit(i, job.preset.name)

            # Use the specific track for this job if provided, otherwise fallback to default
            current_track = job.track if job.track is not None else self._track
            
            # Prepare audio for this track if needed
            audio_path = self._audio_path
            if audio_path is None and any(seg.audio_file for seg in current_track.segments):
                track_id = id(current_track)
                if track_id in track_audio_cache:
                    audio_path = track_audio_cache[track_id]
                else:
                    try:
                        audio_path = self._prepare_track_audio(current_track)
                        track_audio_cache[track_id] = audio_path
                    except Exception as e:
                        _LOGGER.error("Failed to prepare audio for track: %s", e)
                        job.status = "failed"
                        job.error_message = f"Audio preparation failed: {e}"
                        failed += 1
                        self.job_error.emit(i, str(e))
                        continue

            try:
                export_video(
                    self._video_path,
                    current_track,
                    Path(job.output_path),
                    on_progress=lambda total, cur, idx=i: self.job_progress.emit(idx, total, cur),
                    audio_path=audio_path,
                    scale_width=job.preset.width,
                    scale_height=job.preset.height,
                    codec=job.preset.codec,
                    overlay_path=self._overlay_path,
                    image_overlays=self._image_overlays,
                    text_overlays=self._text_overlays,
                    mix_with_original_audio=self._mix_with_original_audio,
                    video_volume=self._video_volume,
                    audio_volume=self._audio_volume,
                )
                job.status = "completed"
                succeeded += 1
                self.job_finished.emit(i, job.output_path)
            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                failed += 1
                self.job_error.emit(i, str(e))

        self._cleanup_temp_dirs()
        self.all_finished.emit(len(self._jobs), succeeded, failed)

    def _prepare_track_audio(self, track: SubtitleTrack) -> Path:
        from src.services.audio_regenerator import AudioRegenerator
        
        temp_dir = Path(tempfile.mkdtemp(prefix="batch_worker_audio_"))
        self._temp_dirs.append(temp_dir)
        output_audio = temp_dir / f"track_tts_{uuid.uuid4().hex[:8]}.mp3"

        regenerated_path, _ = AudioRegenerator.regenerate_track_audio(
            track=track,
            output_path=output_audio,
            video_audio_path=None,
            bg_volume=self._video_volume,
            tts_volume=self._audio_volume,
            apply_segment_volumes=self._apply_segment_volumes,
        )
        return regenerated_path

    def _cleanup_temp_dirs(self) -> None:
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._temp_dirs = []
