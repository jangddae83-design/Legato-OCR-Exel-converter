# Scratchpad

## Current Task: Implementing Enterprise Grade Security Architecture
- **Date**: 2025-12-19
- **Goal**: Refactor UI to State Machine & Implement 7-Layer Security Defense.

### Log
- **Plan Approved**: Enterprise Grade Security (Private Temp, UUID, Limit, Pixel Bomb, Atomic Save).
- **Impl Complete**:
    - **Security Core**: `copy_limited`, `validate_image_security` implemented in `src/app.py`.
    - **State Machine**: Refactored `main()` to use `ui_step` (Upload -> Process -> Error).
    - **Secure Handler**: `handle_file_upload_secure` with 7-Layer Defense.
    - **Config Fix**: Downgraded model to `gemini-2.0-flash-exp` to resolve logic & quota errors.
- **Verification**: Verified via restart & manual walkthrough.
- **Update**: Upgraded model to `gemini-3-flash-preview` per user request.
- **Update**: Upgraded model to `gemini-3-flash` (Stable) for better performance and cost efficiency.
- **Rollback**: Switching back to `gemini-1.5-flash` due to restrictive free tier rate limits (5 RPM) on Gemini 3.
- **Fix**: Resolved "Silent Failure" in Excel conversion.
    - **Refactor**: Implemented `ConversionResult` DTO for type safety.
    - **Security**: Added Excel Formula Injection sanitization.
    - **Performance**: Optimized preview generation (Top 50 rows limit).
    - **UX**: Fixed atomic session state updates to ensure UI consistency.
- **Status**: Committing fixes.
