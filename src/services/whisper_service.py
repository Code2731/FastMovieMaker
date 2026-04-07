"""Whisper transcription service using faster-whisper (CTranslate2, no Qt dependency)."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

from faster_whisper import WhisperModel

from src.models.subtitle import SubtitleSegment, SubtitleTrack
from src.utils.time_utils import seconds_to_ms


def _logprob_to_confidence_pct(avg_logprob: float) -> int:
    """Convert faster-whisper avg_logprob to an integer confidence percentage (0-100)."""
    return min(100, max(0, int(100 * math.exp(avg_logprob))))


def load_model(model_name: str) -> WhisperModel:
    """Load a faster-whisper model onto GPU if available.

    Uses float16 on CUDA for ~4x speed vs openai-whisper with half VRAM.
    Falls back to int8 on CPU for decent speed without GPU.
    """
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except ImportError:
        has_cuda = False

    if has_cuda:
        return WhisperModel(model_name, device="cuda", compute_type="float16")
    else:
        return WhisperModel(model_name, device="cpu", compute_type="int8")


def transcribe(
    model: WhisperModel,
    audio_path: Path,
    language: str = "ko",
    on_progress: Callable[[int, int], None] | None = None,
    on_segment: Callable[[SubtitleSegment], None] | None = None,
    check_cancelled: Callable[[], bool] | None = None,
    on_language_detected: Callable[[str, float], None] | None = None,
    on_segment_confidence: Callable[[SubtitleSegment, int], None] | None = None,
) -> SubtitleTrack:
    """Transcribe audio file and return a SubtitleTrack.

    Args:
        model: Loaded faster-whisper model.
        audio_path: Path to audio file (WAV, MP3, etc.).
        language: Language code, or "auto" for automatic detection.
        on_progress: Callback(current_segment, total_segments) for progress.
        on_segment: Callback(segment) called immediately when a segment is transcribed.
        check_cancelled: Callback returning True if operation should abort.
        on_language_detected: Callback(language_code, probability) after language detection.
        on_segment_confidence: Callback(segment, confidence_pct 0-100) per segment.

    Returns:
        SubtitleTrack with transcribed segments. Returns partial track if cancelled.
    """
    # "auto"이면 None으로 전달해 faster-whisper 자동 감지 활성화
    faster_whisper_language: str | None = None if language == "auto" else language

    # chunk_length=5: 5초 단위 청크로 세그먼트가 더 자주 나와 취소 체크가 빨리 반영됨
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=faster_whisper_language,
        vad_filter=True,
        chunk_length=5,
    )

    # 첫 번째 transcribe 호출 후 감지된 언어를 콜백으로 전달
    detected_language = getattr(info, "language", None) or language
    if on_language_detected is not None:
        lang_prob = float(getattr(info, "language_probability", 1.0))
        on_language_detected(detected_language, lang_prob)

    track = SubtitleTrack(language=detected_language)

    count = 0
    for seg in segments_iter:
        if check_cancelled and check_cancelled():
            break

        new_segment = SubtitleSegment(
            start_ms=seconds_to_ms(seg.start),
            end_ms=seconds_to_ms(seg.end),
            text=seg.text.strip(),
        )
        track.add_segment(new_segment)

        if on_segment:
            on_segment(new_segment)

        if on_segment_confidence is not None:
            avg_logprob = getattr(seg, "avg_logprob", 0.0)
            on_segment_confidence(new_segment, _logprob_to_confidence_pct(avg_logprob))

        count += 1
        if on_progress:
            on_progress(count, 0)

    return track


def release_model(model: WhisperModel) -> None:
    """Release model and free GPU memory."""
    del model
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
