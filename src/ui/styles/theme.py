"""UI 테마 및 색상 상수 관리."""

from PySide6.QtGui import QColor, QBrush

class TimelineTheme:
    # Background
    BG = QColor(18, 18, 18)
    RULER_BG = QColor(25, 25, 25)
    RULER_TICK = QColor(60, 60, 60)
    RULER_TEXT = QColor(140, 140, 140)

    # Subtitle Segments
    SEGMENT_TOP = QColor(60, 140, 220)
    SEGMENT_BOT = QColor(40, 100, 180)
    SEGMENT_BORDER = QColor(80, 170, 255)
    SELECTED_BORDER = QColor(100, 220, 255)
    SELECTED_GLOW = QColor(100, 220, 255, 60)

    # Snap & Playhead
    SNAP_GUIDE = QColor(255, 255, 0, 200)
    PLAYHEAD = QColor(255, 60, 80)
    PLAYHEAD_LINE = QColor(255, 60, 80, 200)

    # Audio (TTS)
    AUDIO_TOP = QColor(80, 180, 100)
    AUDIO_BORDER = QColor(100, 200, 120)

    # BGM
    BGM_TOP = QColor(100, 80, 200)
    BGM_BOT = QColor(60, 40, 160)
    BGM_BORDER = QColor(130, 100, 240)
    BGM_SELECTED_BORDER = QColor(100, 220, 255)
    BGM_SELECTED_BG = QColor(40, 20, 100)

    # Badges
    CORRECTION_BADGE = QBrush(QColor(255, 210, 60, 220))
    ANIMATION_BADGE = QBrush(QColor(80, 160, 255, 220))

    # Waveform
    WAVEFORM_FILL = QColor(255, 140, 40, 120)
    WAVEFORM_EDGE = QColor(255, 180, 80, 200)
    WAVEFORM_CENTER = QColor(255, 220, 150)

    # Overlays (Image)
    IMG_OVERLAY = QColor(160, 90, 220, 180)
    IMG_OVERLAY_BORDER = QColor(190, 120, 240)
    IMG_OVERLAY_SELECTED_BG = QColor(0, 100, 140)

    # Overlays (Text)
    TEXT_OVERLAY = QColor(255, 180, 80, 180)
    TEXT_OVERLAY_BORDER = QColor(255, 200, 120)
    TEXT_OVERLAY_SELECTED_BG = QColor(255, 140, 40)
    TEXT_OVERLAY_SELECTED_BORDER = QColor(255, 220, 160)

    # Volume
    VOLUME_LINE = QColor(255, 255, 255, 200)
    VOLUME_POINT = QColor(255, 255, 255)

    # Clips & Transitions
    CLIP_SELECTED_BORDER = QColor(100, 220, 255)
    CLIP_SELECTED_BG = QColor(0, 100, 140)
    TRANSITION_MARKER = QColor(255, 215, 0, 180)

    # Source Colors (for track identification)
    SOURCE_COLORS = [
        (QColor(0, 160, 160), QColor(0, 120, 120), QColor(0, 200, 200)),
        (QColor(200, 120, 40), QColor(160, 90, 20), QColor(230, 150, 60)),
        (QColor(140, 70, 190), QColor(100, 40, 150), QColor(170, 100, 220)),
        (QColor(60, 160, 80), QColor(40, 120, 50), QColor(90, 190, 110)),
        (QColor(200, 60, 80), QColor(150, 40, 60), QColor(230, 90, 110)),
        (QColor(70, 110, 200), QColor(40, 80, 160), QColor(100, 140, 230)),
    ]

    # Marker Colors
    MARKER_COLORS: dict[str, QColor] = {
        "yellow": QColor(255, 220, 50),
        "red":    QColor(220, 80,  80),
        "green":  QColor(80,  200, 80),
        "blue":   QColor(80,  150, 220),
        "white":  QColor(220, 220, 220),
    }

    # Label Colors (top, bottom, border)
    LABEL_COLORS: dict[str, tuple[QColor, QColor, QColor]] = {
        "red":    (QColor(220, 80, 80),   QColor(180, 50, 50),   QColor(255, 110, 110)),
        "orange": (QColor(220, 150, 70),  QColor(180, 110, 40),  QColor(255, 180, 100)),
        "yellow": (QColor(200, 200, 70),  QColor(160, 160, 40),  QColor(230, 230, 100)),
        "green":  (QColor(80, 180, 80),   QColor(50, 140, 50),   QColor(110, 210, 110)),
        "blue":   (QColor(70, 130, 220),  QColor(40, 90, 180),   QColor(100, 160, 255)),
        "purple": (QColor(160, 80, 200),  QColor(120, 40, 160),  QColor(190, 110, 230)),
        "pink":   (QColor(220, 100, 160), QColor(180, 60, 120),  QColor(255, 130, 190)),
    }

    # Drag & Drop Markers
    INSERT_MARKER = QColor(255, 255, 0)
    INSERT_MARKER_COPY = QColor(0, 255, 0)
