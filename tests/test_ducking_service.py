"""Tests for DuckingService.build_volume_expr()."""

from src.models.subtitle import SubtitleSegment
from src.services.ducking_service import DuckingService


def _make_seg(start_ms: int, end_ms: int, has_audio: bool = True) -> SubtitleSegment:
    return SubtitleSegment(
        start_ms=start_ms,
        end_ms=end_ms,
        text="test",
        audio_file="/tmp/test.mp3" if has_audio else None,
    )


def test_empty_segments_returns_base_volume_literal() -> None:
    result = DuckingService.build_volume_expr([], base_volume=0.8, duck_volume=0.3)
    assert result == "0.8"


def test_segments_without_audio_are_ignored() -> None:
    segs = [_make_seg(0, 2000, has_audio=False), _make_seg(3000, 5000, has_audio=False)]
    result = DuckingService.build_volume_expr(segs, base_volume=0.5, duck_volume=0.2)
    assert result == "0.5"


def test_zero_attack_release_keeps_legacy_window_shape() -> None:
    segs = [_make_seg(500, 2000)]
    result = DuckingService.build_volume_expr(
        segs,
        base_volume=0.8,
        duck_volume=0.3,
        attack_ms=0,
        release_ms=0,
        merge_gap_ms=0,
    )
    assert "between(t,0.500,2.000)" in result
    assert "0.300" in result
    assert "0.800" in result
    assert "if(lt(t" not in result


def test_attack_release_add_smoothing_expression() -> None:
    segs = [_make_seg(1000, 3000)]
    result = DuckingService.build_volume_expr(
        segs,
        base_volume=1.0,
        duck_volume=0.25,
        attack_ms=120,
        release_ms=240,
        merge_gap_ms=150,
    )
    # release extends window end by 0.240s
    assert "between(t,1.000,3.240)" in result
    assert "if(lt(t,1.120)" in result
    assert "if(lt(t,3.000)" in result


def test_merge_gap_merges_adjacent_windows() -> None:
    segs = [_make_seg(0, 1000), _make_seg(1050, 2000)]
    merged = DuckingService.build_volume_expr(
        segs,
        base_volume=0.8,
        duck_volume=0.3,
        attack_ms=0,
        release_ms=0,
        merge_gap_ms=100,
    )
    # merged into single window [0, 2.0]
    assert merged.count("between(") == 2  # one mask + one masked value
    assert "between(t,0.000,2.000)" in merged


def test_merge_gap_keeps_separate_windows_when_gap_is_large() -> None:
    segs = [_make_seg(0, 1000), _make_seg(1300, 2000)]
    separate = DuckingService.build_volume_expr(
        segs,
        base_volume=0.8,
        duck_volume=0.3,
        attack_ms=0,
        release_ms=0,
        merge_gap_ms=100,
    )
    assert "between(t,0.000,1.000)" in separate
    assert "between(t,1.300,2.000)" in separate


def test_audio_segments_only_affect_windows() -> None:
    segs = [
        _make_seg(0, 1000, has_audio=True),
        _make_seg(2000, 3000, has_audio=False),
        _make_seg(4000, 5000, has_audio=True),
    ]
    result = DuckingService.build_volume_expr(
        segs,
        base_volume=0.7,
        duck_volume=0.2,
        attack_ms=0,
        release_ms=0,
        merge_gap_ms=0,
    )
    assert "between(t,0.000,1.000)" in result
    assert "between(t,4.000,5.000)" in result
    assert "between(t,2.000,3.000)" not in result
