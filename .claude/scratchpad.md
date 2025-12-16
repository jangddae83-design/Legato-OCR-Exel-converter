# Scratchpad

## Current Task: Initial Setup & MVP Implementation

**Goal**: Smart Layout OCR to Excel (S-LOE) 프로젝트 초기 설정 및 핵심 기능 구현.

### Progress
- [x] Spec Kit 설치 및 초기화 (`specify init`).
- [x] Constitution (`.specify/memory/constitution.md`) 작성 (GEMINI.md 기준).
- [x] Spec (`spec.md`) 및 Plan (`plan.md`), Tasks (`tasks.md`) 작성.
- [x] Phase 1: 기본 프로젝트 구조 설정 Model 정의 (`src/core/models.py`).
- [x] Phase 2: Core Logic 구현.
    - Analyzer Service (`src/core/analyzer_service.py`): Gemini 연동 (Mock 지원).
    - Excel Service (`src/core/excel_service.py`): OpenPyXL 렌더링.
- [x] Phase 3: Android UI 구현.
    - Streamlit App (`src/app.py`): 파일 업로드 -> 변환 -> 다운로드 UI.

### Next Steps
- [x] 실행 테스트 (API Key 설정 완료, Gemini 3 Pro Preview 모델 적용).
- [x] 배포 가이드 문서 작성 (DEPLOYMENT.md, README.md).
- [ ] Gemini Prompt 튜닝 (실제 이미지 테스트 후 필요 시).
- [ ] 복잡한 레이아웃 (병합된 헤더 등) 검증.

### Issues / Notes
- Streamlit Cloud 배포를 위한 `requirements.txt` 버전 고정 완료.
- `gemini-3.0-pro` 모델명 오류 수정 -> `gemini-3-pro-preview`로 변경.
- Pydantic 모델 스키마 오류 수정 (기본값 제거 및 프롬프트 강화).
- API Key 설정 완료 (`.env` 생성). Git에 커밋되지 않도록 주의.
