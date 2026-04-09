from pathlib import Path

from unittest.mock import patch

from src.models.subtitle import SubtitleSegment, SubtitleTrack
from src.ui.dialogs.export_dialog import ExportDialog


def test_export_dialog_worker_status_updates_label(qtbot):
    dialog = ExportDialog(Path("video.mp4"), SubtitleTrack(), video_has_audio=False)
    qtbot.addWidget(dialog)

    dialog._on_worker_status("GPU export failed, retrying with software encoder...")
    assert "retrying with software encoder" in dialog._status_label.text().lower()


@patch(
    "src.ui.dialogs.export_dialog.get_hw_info",
    return_value={
        "platform": "darwin",
        "recommended": "h264_videotoolbox",
        "candidates": ["h264_videotoolbox", "libx264"],
        "unavailable_reasons": {},
    },
)
def test_export_dialog_shows_planned_encoder_label(mock_hw_info, qtbot):
    dialog = ExportDialog(Path("video.mp4"), SubtitleTrack(), video_has_audio=False)
    qtbot.addWidget(dialog)
    assert "h264_videotoolbox" in dialog._encoder_label.text().lower()


@patch(
    "src.ui.dialogs.export_dialog.get_hw_info",
    return_value={
        "platform": "darwin",
        "recommended": "libx264",
        "candidates": ["libx264"],
        "unavailable_reasons": {"videotoolbox": "encoder help probe failed"},
    },
)
def test_export_dialog_gpu_tooltip_contains_unavailable_reason(mock_hw_info, qtbot):
    dialog = ExportDialog(Path("video.mp4"), SubtitleTrack(), video_has_audio=False)
    qtbot.addWidget(dialog)
    assert not dialog._gpu_checkbox.isEnabled()
    tooltip = dialog._gpu_checkbox.toolTip().lower()
    assert "videotoolbox" in tooltip


def test_ducking_attack_release_inputs_follow_checkbox_state(qtbot):
    track = SubtitleTrack(segments=[SubtitleSegment(0, 1000, "hi", audio_file="/tmp/a.mp3")])
    dialog = ExportDialog(Path("video.mp4"), track, video_has_audio=True)
    qtbot.addWidget(dialog)

    assert dialog._ducking_checkbox.isEnabled()
    assert not dialog._duck_attack_spin.isEnabled()
    assert not dialog._duck_release_spin.isEnabled()

    dialog._ducking_checkbox.setChecked(True)
    assert dialog._duck_slider.isEnabled()
    assert dialog._duck_attack_spin.isEnabled()
    assert dialog._duck_release_spin.isEnabled()

    dialog._ducking_checkbox.setChecked(False)
    assert not dialog._duck_slider.isEnabled()
    assert not dialog._duck_attack_spin.isEnabled()
    assert not dialog._duck_release_spin.isEnabled()


@patch("src.services.audio_regenerator.AudioRegenerator.regenerate_track_audio")
def test_prepare_tts_audio_passes_ducking_smoothing_params(mock_regen, qtbot, tmp_path):
    track = SubtitleTrack(segments=[SubtitleSegment(0, 1000, "hi", audio_file="/tmp/a.mp3")])
    out = tmp_path / "regen.mp3"
    out.write_text("dummy", encoding="utf-8")
    mock_regen.return_value = (out, 1000)

    dialog = ExportDialog(Path("video.mp4"), track, video_has_audio=True)
    qtbot.addWidget(dialog)
    dialog._ducking_checkbox.setChecked(True)
    dialog._duck_slider.setValue(35)
    dialog._duck_attack_spin.setValue(150)
    dialog._duck_release_spin.setValue(260)

    dialog._prepare_tts_audio()

    kwargs = mock_regen.call_args.kwargs
    assert kwargs["ducking_enabled"] is True
    assert kwargs["duck_level"] == 0.35
    assert kwargs["duck_attack_ms"] == 150
    assert kwargs["duck_release_ms"] == 260
    assert kwargs["duck_merge_gap_ms"] == 150
