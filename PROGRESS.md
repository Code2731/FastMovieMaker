# FastMovieMaker - 개발 진행 과정

---

## 현재 상태 및 미구현 사항

**현재 상태:** Day 29 완료 (2026-04-25)

**참고:** MS Store Python 3.13 사용 (3.9 호환성 고려 불필요)

---

### 구현 완료 요약

| 기능 | 상태 |
|------|------|
| Phase 1: 자막 편집 기초 | 완료 |
| Phase 2: AI 자동화 (Whisper/TTS) | 완료 |
| Phase 3: 타임라인 & 오디오 시각화 | 완료 |
| Phase 4: 프로 워크플로우 (Step 1-2) | 완료 |
| **Day 28: 트랙 관리 및 정합성 강화** | **완료** |
| **Day 29: CPython 전환 안정화 및 버그 수정** | **완료** |

---

### 상세 진행 기록

#### Day 29 (2026-04-25)
- **타임라인 썸네일 미표시 근본 원인 수정**:
    - `main_window._project`(초기 객체)와 `ctx.project`(로드 후 갱신 객체)가 분리되어 `_refresh_all_widgets`가 구 프로젝트로 타임라인을 덮어쓰던 버그 수정.
    - `_refresh_all_widgets`, `_ensure_timeline_duration`, `_refresh_track_selector`, `_update_project_duration`에서 `self._ctx.project` 직접 참조로 변경.
- **CPython(MS Store Python 3.13) 전환 후 테스트 실패 47개 전면 수정**:
    - `commands.py`: `AutoAlignSubtitlesCommand.undo()` end_ms 미복원 버그 수정.
    - `commands.py`: `EditColorCorrectionCommand`, `AddMarkerCommand`, `RemoveMarkerCommand`, `RenameMarkerCommand`, `ApplyTTSVerificationCommand` 5개 커맨드 클래스 추가.
    - `clip_controller.py`: `on_delete_selected_clips()` 메서드 추가.
    - `track_header_panel.py`: 상수 4개 추가, `SubtitleTrack` 빈 상태 falsy 버그 수정.
    - `timeline_painter.py`: `_source_color_cache` 초기화 속성 추가.
- **pytest 환경 안정화**:
    - MS Store Python WinError 448(심볼릭링크 resolve 실패) 로 인한 pytest cleanup 크래시 수정 (`conftest.py` 패치).
    - faster-whisper `model.bin` 0바이트(손상) 시 실제 모델 의존 테스트 skip 처리.
- **결과**: 990 passed, 3 skipped, EXIT=0

#### Day 28 (2026-03-01)
- **트랙 관리 시스템 완성**:
    - `TrackHeaderPanel` 시그널 완전 연동 (비디오/BGM 트랙 추가, 삭제, 이름 변경).
    - `RenameVideoTrackCommand`, `AddAudioTrackCommand`, `RenameAudioTrackCommand` 등 관련 Undo 커맨드 구현.
    - `ClipController` 및 `MediaController`에 트랙 관리 핸들러 추가.
- **타임라인 시각적 피드백 개선**:
    - **잠긴(Locked) 트랙**: 클립 위에 어두운 오버레이와 자물쇠 아이콘 렌더링 구현 (`TimelinePainter`).
    - **숨겨진(Hidden) 트랙**: 상태 연동 및 실시간 플레이어/UI 업데이트 최적화.
- **프로젝트 정합성 및 버그 수정**:
    - **프로젝트 길이 관리 단일화**: `AppContext.update_project_duration()`을 통해 모든 트랙(비디오, 자막, 오디오, BGM)의 최대 길이를 자동으로 계산하도록 통합.
    - **영상 드롭 분할 버그 수정**: 기존 클립 위에 영상 드롭 시 커맨드 없이 분할되던 로직을 `SplitClipCommand`와 매크로를 사용하도록 수정하여 Undo 정합성 확보.
    - **다중 트랙 분할 로직 개선**: Ctrl+B 단축키 사용 시 선택된 클립이 있는 트랙을 우선적으로 분할하도록 보완.
- **코드 품질 개선**:
    - `ClipController` 내 중복 메서드 제거 및 `AppContext` 콜백 기반 아키텍처 강화.

#### Day 27 (2026-02-20)
- **비디오 썸네일 버그 수정**: 
    - 줌 인 시 썸네일이 비정상적으로 밀리거나 누락되는 좌표 계산 이슈 해결.
    - `TimelineThumbnailService`의 캐시 키 생성 로직 개선.
- **성능 최적화**: 타임라인 렌더링 시 보이지 않는 구간의 썸네일 요청 원천 차단.
- **단위 테스트 안정화**: `test_timeline_thumbnail_service.py` 포함 전체 테스트 100% 통과 (469/469).

... (이하 기존 내용 동일) ...
