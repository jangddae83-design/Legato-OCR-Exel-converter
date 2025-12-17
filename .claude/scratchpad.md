# Scratchpad

## Current Task: Security Hardening & UI Polish

**Goal**: Smart Layout OCR to Excel (S-LOE) 보안 강화 및 UI 사용자 경험 개선.

### Progress
- [x] Spec Kit 설치 및 초기화 (`specify init`).
- [x] Constitution (`.specify/memory/constitution.md`) 작성 (GEMINI.md 기준).
- [x] Spec (`spec.md`) 및 Plan (`plan.md`), Tasks (`tasks.md`) 작성.
- [x] Phase 1: 기본 프로젝트 구조 설정 Model 정의 (`src/core/models.py`).
- [x] Phase 2: Core Logic 구현.
    - Analyzer Service (`src/core/analyzer_service.py`): Gemini 연동 (Mock 지원).
    - Excel Service (`src/core/excel_service.py`): OpenPyXL 렌더링.
- [x] Phase 3: UI Implementation.
    - Streamlit App (`src/app.py`): 파일 업로드 -> 변환 -> 다운로드 UI.
- [x] Phase 4: Security Hardening (P0/P1 Fixes).
    - Auth Logic Fix (Zero-trust).
    - Thread-safe API Lock & Timeout.
    - Image Decompression Bomb Defense.
    - HMAC Cache Isolation.
- [x] Phase 5: UI Layout Upgrade.
    - Persistent Split View (Top: Image, Bottom: Excel).
    - Excel Preview (Top 100 rows).
    - `st.session_state` optimization (`on_change` callback).

### Next Steps
- [ ] Streamlit Cloud 배포 및 최종 점검.
- [ ] 사용자 피드백 수집 및 추가 기능 검토.

### Issues / Notes
- Streamlit Cloud 배포를 위한 `requirements.txt` 버전 고정 완료.
- `gemini-3.0-pro` 모델명 오류 수정 -> `gemini-3-pro-preview`로 변경.
- Pydantic 모델 스키마 오류 수정 (기본값 제거 및 프롬프트 강화).
- API Key 설정 완료 (`.env` 생성). Git에 커밋되지 않도록 주의.
- **Security**: HMAC 캐시 격리로 다중 사용자 간 데이터 유출 원천 차단.
- **UX**: 대용량 엑셀 미리보기 시 성능 저하 방지를 위해 상위 100행 제한 적용.
