Read docs TECHSPEC.md before conducting your work.

# CLAUDE.md — FastMovieMaker 코딩 가이드라인

## 0. 코딩 규율 (Coding Discipline)

### 0.1 코딩 전에 생각하기
- 가정을 명시적으로 말할 것. 불확실하면 물어볼 것.
- 여러 해석이 가능하면 제시할 것 — 조용히 하나를 선택하지 말 것.
- 더 단순한 접근이 있으면 말할 것. 필요하면 반론을 제기할 것.
- 뭔가 불명확하면 멈추고. 뭐가 헷갈리는지 말하고. 물어볼 것.

### 0.2 단순함 우선 (Simplicity First)
- 요청받은 것 이상의 기능 추가 금지.
- 한 번만 쓰는 코드에 추상화 금지.
- 요청하지 않은 "유연성"이나 "설정 가능성" 금지.
- 불가능한 시나리오에 대한 에러 처리 금지.
- 200줄로 작성했는데 50줄로 가능하면, 다시 작성할 것.

**자문: "시니어 개발자가 이거 너무 복잡하다고 할까?" → 그렇다면 단순화.**

### 0.3 외과적 변경 (Surgical Changes)
기존 코드 수정 시:
- 주변 코드, 주석, 포맷팅을 "개선"하지 말 것.
- 고장나지 않은 것을 리팩토링하지 말 것.
- 기존 스타일을 따를 것 (다르게 하고 싶어도).
- 관련 없는 죽은 코드 발견 시: 언급만 하고, 삭제하지 말 것.

**내 변경으로 생긴 고아 코드만 정리:**
- 내 변경으로 사용되지 않게 된 import/변수/함수만 제거.
- 기존 죽은 코드는 요청받기 전까지 삭제 금지.

**테스트: 모든 변경된 줄은 사용자 요청에 직접 연결되어야 한다.**

### 0.4 목표 지향 실행 (Goal-Driven Execution)
작업을 검증 가능한 목표로 변환:
- "유효성 검사 추가" → "잘못된 입력 테스트 작성 후 통과시키기"
- "버그 수정" → "재현 테스트 작성 후 통과시키기"
- "X 리팩토링" → "리팩토링 전후로 테스트 통과 확인"

다단계 작업 시 간단한 계획:
```
1. [단계] → 검증: [확인 방법]
2. [단계] → 검증: [확인 방법]
3. [단계] → 검증: [확인 방법]
```

---

## 1. 기본 원칙
- 한국어로 응답
- 구체적일수록 좋은 결과
- 한 번에 너무 많은 일을 시키지 말 것
- 코드 작성 시 "왜 이렇게 짰는지" 설명
- 예외 처리 철저히
- 주석은 한국어로 핵심만
- 타입 힌트 필수 (PEP 484)
- docstring은 간단히 (한 줄)

---

## 2. 프로젝트 아키텍처

### 3-Layer 구조
```
src/
├── models/        # 순수 Python 데이터클래스 (Qt 독립)
├── services/      # 비즈니스 로직 (동기 기본, 네트워크 I/O만 async)
├── infrastructure/# FFmpeg runner, transcriber 등 외부 도구 래퍼
├── ui/            # PySide6 위젯 + 컨트롤러
│   ├── controllers/  # MainWindow에서 분리된 로직 컨트롤러
│   └── dialogs/      # 모달 다이얼로그
├── workers/       # QThread moveToThread() 패턴 백그라운드 작업
└── utils/         # i18n, config, time_utils, hw_accel
```

### 핵심 규칙
- **models/**: Qt 의존 금지, 순수 데이터만
- **services/**: Qt Signal 금지, 동기 코드 기본
- **workers/**: moveToThread() 패턴 사용, Signal/Slot 비동기 통신
- **시간 단위**: 항상 ms (int), frame 변환 시 fps 함께 전달

### 새 기능 추가 시
```
1. src/models/xxx.py       → 순수 데이터클래스
2. src/services/xxx.py     → 비즈니스 로직
3. tests/test_xxx.py       → 단위테스트 (Qt 의존 X)
4. src/workers/xxx_worker.py → UI 연결 (필요시)
```

---

## 3. 테스트 규칙

```bash
# 단일 파일
pytest tests/test_xxx.py -v

# 특정 테스트
pytest tests/test_xxx.py::TestClass::test_method -v

# 전체 (414+ 테스트)
pytest tests/ -v
```

- `test_models.py`: Qt 없이 실행
- `test_*_gui.py`: Qt 필요 (pytest-qt)
- Mock 패턴: `unittest.mock.patch()` (FFmpeg, Whisper 등)
- 버그 수정 시: **재현 테스트 먼저 작성 → 수정 → 통과 확인**

---

## 4. FFmpeg / 미디어 처리

- FFmpeg 경로: `E:\Python\Scripts\ffmpeg.exe` 또는 `src/infrastructure/ffmpeg_runner.py`
- 명령어 로깅: `src/services/ffmpeg_logger.py` 사용
- 시간 관련 수정 시: `time_utils.py` 테스트 먼저 → UI 반영
- Whisper: 장시간 작업은 progress bar + 취소 지원 필수

---

## 5. 환경

- **Python**: 3.13+ (venv: `.venv/Scripts/python.exe`)
- **실행**: `".venv/Scripts/python.exe" main.py`
- **플랫폼**: Windows 11, NVIDIA RTX 3080
- **주요 의존성**: PySide6, openai-whisper, torch (CUDA 12.4), edge-tts, ffmpeg-python

---

마지막 업데이트: 2026-02-20
