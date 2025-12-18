# Project Scratchpad

## Current Task: Responsive Layout & UX Improvements
- **Date**: 2025-12-18
- **Goal**: Implement split view for desktop, stacked for mobile, and improve state management.
- **Status**: Completed.

## Changelog
- **refactor(app)**: `layout='wide'`로 변경 및 `st.columns` 적용 (Desktop: Split, Mobile: Stack).
- **feat(state)**: 파일/크롭 변경 시 결과 패널 즉시 초기화 (ID Matching 도입).
- **fix(styles)**: 모바일 반응형을 위한 `use_container_width=True` 적용.
- **fix(excel)**: 다운로드 버튼의 `mime` 타입 제거로 브라우저 호환성 해결.
