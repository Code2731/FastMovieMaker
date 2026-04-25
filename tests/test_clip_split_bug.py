import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack

# Create a global application instance
app = QApplication.instance() or QApplication(sys.argv)

from unittest.mock import MagicMock
from src.models.project import ProjectState
from src.models.video_clip import VideoClip, VideoClipTrack
from src.ui.controllers.clip_controller import ClipController
from src.ui.controllers.app_context import AppContext

# Mock i18n
import src.ui.controllers.clip_controller as clip_ctrl_module
clip_ctrl_module.tr = lambda x: x

def test_split_clip_with_multiple_videos():
    ctx = AppContext()
    ctx.project = ProjectState()
    
    vt = VideoClipTrack()
    vt.clips = [
        VideoClip(0, 5000, source_path="A.mp4"),
        VideoClip(0, 5000, source_path="B.mp4")
    ]
    ctx.project.video_tracks = [vt]
    
    # Real undo stack to execute redo()
    ctx.undo_stack = QUndoStack()
    ctx.window = MagicMock()
    ctx.player = MagicMock()
    ctx.player.playbackState.return_value = MagicMock()
    ctx.timeline = MagicMock()
    ctx.timeline.get_playhead.return_value = 7500
    ctx.timeline.get_selected_item.return_value = ("none", -1, -1)
    ctx.status_bar_mock = MagicMock()
    ctx.window.statusBar.return_value = ctx.status_bar_mock

    ctx.refresh_all = MagicMock()

    controller = ClipController(ctx)
    controller.on_split_clip(-1, 7500)
    
    assert len(vt.clips) == 3, f"T1: Expected 3 clips, got {len(vt.clips)}"
    assert vt.clips[1].source_path == "B.mp4"
    print("test_split_clip_with_multiple_videos passed!")

def test_split_clip_multiple_tracks():
    ctx = AppContext()
    ctx.project = ProjectState()
    
    vt0 = VideoClipTrack()
    vt0.clips = [VideoClip(0, 10000, source_path="A.mp4")]
    vt1 = VideoClipTrack()
    vt1.clips = [VideoClip(0, 10000, source_path="B.mp4")]
    ctx.project.video_tracks = [vt0, vt1]
    
    ctx.undo_stack = QUndoStack()
    ctx.window = MagicMock()
    ctx.player = MagicMock()
    ctx.player.playbackState.return_value = MagicMock()
    ctx.timeline = MagicMock()
    ctx.timeline.get_playhead.return_value = 3000
    ctx.timeline.get_selected_item.return_value = ("none", -1, -1)
    ctx.status_bar_mock = MagicMock()
    ctx.window.statusBar.return_value = ctx.status_bar_mock

    ctx.refresh_all = MagicMock()

    controller = ClipController(ctx)
    controller.on_split_clip(-1, 3000)
    
    assert len(ctx.project.video_tracks[1].clips) == 2, f"T2: Expected 2 clips on track 1, got {len(ctx.project.video_tracks[1].clips)}"
    print("test_split_clip_multiple_tracks passed!")

if __name__ == "__main__":
    try:
        test_split_clip_with_multiple_videos()
        test_split_clip_multiple_tracks()
        print("All reproduction tests passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
