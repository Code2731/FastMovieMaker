"""BGM ducking service - FFmpeg volume expressions for TTS-aware BGM volume control."""

from __future__ import annotations

from src.models.subtitle import SubtitleSegment


class DuckingService:
    """Creates FFmpeg volume expressions to duck BGM during TTS playback."""

    @staticmethod
    def build_volume_expr(
        segments: list[SubtitleSegment],
        base_volume: float,
        duck_volume: float,
        attack_ms: int = 0,
        release_ms: int = 0,
        merge_gap_ms: int = 0,
    ) -> str:
        """
        Build FFmpeg volume filter expression that ducks BGM during TTS segments.

        Args:
            segments: List of subtitle segments (only those with audio_file are used).
            base_volume: BGM volume outside TTS segments (0.0-1.0).
            duck_volume: BGM volume during TTS segments (0.0-1.0).
            attack_ms: Fade-down duration when entering ducking window.
            release_ms: Fade-up duration when exiting ducking window.
            merge_gap_ms: Merge adjacent TTS windows if gap is <= this value.

        Returns:
            FFmpeg volume expression string, e.g.:
            "if(gt(between(t,0.500,2.000)+between(t,3.000,5.500),0),0.300,0.800)"
            If no active TTS segments, returns str(base_volume).
        """
        active = sorted((s for s in segments if s.audio_file), key=lambda s: s.start_ms)
        if not active:
            return str(base_volume)

        merged_windows = DuckingService._merge_windows(active, merge_gap_ms=max(0, int(merge_gap_ms)))
        attack_s = max(0, int(attack_ms)) / 1000.0
        release_s = max(0, int(release_ms)) / 1000.0
        base = float(base_volume)
        duck = float(duck_volume)

        masks: list[str] = []
        values: list[str] = []
        for start_ms, end_ms in merged_windows:
            start_s = start_ms / 1000.0
            end_s = end_ms / 1000.0
            release_end_s = end_s + release_s
            mask = f"between(t,{start_s:.3f},{release_end_s:.3f})"
            piece = DuckingService._build_window_piece(
                start_s=start_s,
                end_s=end_s,
                base=base,
                duck=duck,
                attack_s=attack_s,
                release_s=release_s,
            )
            masks.append(mask)
            values.append(f"({mask})*({piece})")

        return (
            f"if(gt({'+'.join(masks)},0),"
            f"{'+'.join(values)},"
            f"{base:.3f})"
        )

    @staticmethod
    def _merge_windows(
        segments: list[SubtitleSegment],
        merge_gap_ms: int,
    ) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        for seg in segments:
            seg_start = int(seg.start_ms)
            seg_end = int(seg.end_ms)
            if not windows:
                windows.append((seg_start, seg_end))
                continue
            prev_start, prev_end = windows[-1]
            if seg_start <= prev_end + merge_gap_ms:
                windows[-1] = (prev_start, max(prev_end, seg_end))
            else:
                windows.append((seg_start, seg_end))
        return windows

    @staticmethod
    def _build_window_piece(
        start_s: float,
        end_s: float,
        base: float,
        duck: float,
        attack_s: float,
        release_s: float,
    ) -> str:
        if attack_s <= 0 and release_s <= 0:
            return f"{duck:.3f}"

        if attack_s > 0:
            attack_end_s = start_s + attack_s
            attack_expr = (
                f"({base:.3f}+({duck:.3f}-{base:.3f})"
                f"*((t-{start_s:.3f})/{attack_s:.3f}))"
            )
        else:
            attack_end_s = start_s
            attack_expr = f"{duck:.3f}"

        if release_s > 0:
            release_start_s = end_s
            release_expr = (
                f"({duck:.3f}+({base:.3f}-{duck:.3f})"
                f"*((t-{release_start_s:.3f})/{release_s:.3f}))"
            )
        else:
            release_start_s = end_s
            release_expr = f"{base:.3f}"

        if attack_s > 0 and release_s > 0:
            return (
                f"if(lt(t,{attack_end_s:.3f}),{attack_expr},"
                f"if(lt(t,{release_start_s:.3f}),{duck:.3f},{release_expr}))"
            )
        if attack_s > 0:
            return f"if(lt(t,{attack_end_s:.3f}),{attack_expr},{duck:.3f})"
        return f"if(lt(t,{release_start_s:.3f}),{duck:.3f},{release_expr})"
