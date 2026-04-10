"""Extract audio from video files using FFmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from src.services.ffmpeg_logger import log_ffmpeg_command
from src.infrastructure.ffmpeg_runner import get_ffmpeg_runner
from src.utils.config import AUDIO_SAMPLE_RATE


def extract_audio_to_wav(
    video_path: Path,
    output_path: Path | None = None,
    check_cancelled: callable | None = None,
) -> Path:
    """Extract audio from video as 16kHz mono WAV for Whisper.

    Args:
        video_path: Path to the source video file.
        output_path: Optional output path. If None, creates a temp file.
        check_cancelled: Optional callback to check if extraction is cancelled.

    Returns:
        Path to the extracted WAV file.

    Raises:
        FileNotFoundError: If FFmpeg is not found.
        RuntimeError: If FFmpeg extraction fails or is cancelled.
    """
    runner = get_ffmpeg_runner()
    if not runner.is_available():
        raise FileNotFoundError("FFmpeg not found. Please install FFmpeg.")

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        output_path = Path(tmp.name)

    args = [
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", "1",
        str(output_path),
    ]

    log_ffmpeg_command(args)
    process = runner.run_async(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        while process.poll() is None:
            if check_cancelled and check_cancelled():
                process.terminate()
                process.wait()
                raise RuntimeError("Audio extraction cancelled")
            try:
                process.communicate(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()

    if process.returncode != 0:
        out, err = process.communicate()
        stderr = (err or "")[:500]
        raise RuntimeError(f"FFmpeg failed:\n{stderr}")

    return output_path
