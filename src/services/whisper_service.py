"""Whisper transcription service using faster-whisper (CTranslate2, no Qt dependency)."""

from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Callable

from faster_whisper import WhisperModel

from src.models.subtitle import SubtitleSegment, SubtitleTrack
from src.utils.time_utils import seconds_to_ms

_LOGGER = logging.getLogger(__name__)


def _logprob_to_confidence_pct(avg_logprob: float) -> int:
    """Convert faster-whisper avg_logprob to an integer confidence percentage (0-100)."""
    return min(100, max(0, int(100 * math.exp(avg_logprob))))


def load_model(model_name: str) -> WhisperModel:
    """Load a faster-whisper model onto GPU if available."""
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
    hf_token: str | None = None,
) -> SubtitleTrack:
    """Transcribe audio file and return a SubtitleTrack."""
    faster_whisper_language: str | None = None if language == "auto" else language

    # 1. (Optional) Perform Speaker Diarization
    speaker_segments = []
    if hf_token:
        try:
            from pyannote.audio import Pipeline
            import torch
            
            _LOGGER.info("Starting Speaker Diarization...")
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            # Use GPU if available for pyannote
            if torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))
            
            diarization = pipeline(str(audio_path))
            
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })
            _LOGGER.info("Diarization complete: found %d turns", len(speaker_segments))
        except ImportError:
            _LOGGER.warning("pyannote.audio not installed. Skipping diarization.")
        except Exception as e:
            _LOGGER.error("Speaker diarization failed: %s", e)

    # 2. Transcribe with Whisper
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=faster_whisper_language,
        vad_filter=True,
        chunk_length=5,
    )

    detected_language = getattr(info, "language", None) or language
    if on_language_detected is not None:
        lang_prob = float(getattr(info, "language_probability", 1.0))
        on_language_detected(detected_language, lang_prob)

    track = SubtitleTrack(language=detected_language)

    count = 0
    for seg in segments_iter:
        if check_cancelled and check_cancelled():
            break

        # Match speaker to segment by mid-point
        mid_time = (seg.start + seg.end) / 2.0
        current_speaker = None
        for s_seg in speaker_segments:
            if s_seg["start"] <= mid_time <= s_seg["end"]:
                current_speaker = s_seg["speaker"]
                break
        
        # If no mid-point match, try any overlap
        if not current_speaker:
            for s_seg in speaker_segments:
                if s_seg["start"] < seg.end and s_seg["end"] > seg.start:
                    current_speaker = s_seg["speaker"]
                    break

        new_segment = SubtitleSegment(
            start_ms=seconds_to_ms(seg.start),
            end_ms=seconds_to_ms(seg.end),
            text=seg.text.strip(),
            speaker=current_speaker
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
