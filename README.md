# Legato OCR Excel Converter (S-LOE)

문서 이미지를 분석하여 원본 레이아웃을 유지한 채 엑셀(.xlsx) 파일로 변환해주는 웹 애플리케이션입니다.
Gemini 3 Pro의 강력한 멀티모달 기능을 활용하여 표, 병합된 셀, 텍스트 등을 스마트하게 인식합니다.

## ✨ 주요 기능 (Key Features)
- **이미지 업로드**: PNG, JPG 형식을 지원하며 드래그 앤 드롭으로 쉽게 업로드.
- **AI 레이아웃 분석**: Gemini 3 Pro를 사용하여 표 구조(행, 열, 병합)를 정밀하게 분석.
- **엑셀 렌더링**: 분석된 데이터를 바탕으로 병합된 셀까지 완벽하게 구현된 엑셀 파일 생성.
- **간편한 다운로드**: 변환 완료 후 클릭 한 번으로 결과물 저장.

## 🚀 시작하기 (Getting Started)

### 1. 환경 설정
Python 3.10 이상이 필요합니다.

```bash
# 가상환경 생성 및 실행
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 비밀번호 및 API 키 설정
앱 보안을 위해 `.streamlit/secrets.toml` 파일을 사용하여 비밀번호와 API 키를 관리합니다.
`.streamlit/secrets.toml.example` 파일을 복사하여 설정하세요.

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

**설정 파일 (`.streamlit/secrets.toml`) 예시:**
```toml
[general]
APP_PASSWORD = "admin" # 원하는 비밀번호로 변경하세요

GEMINI_API_KEY = "your_api_key_here"
GEMINI_MODEL_NAME = "gemini-3-pro-preview"
```

✅ **기능**:
- **비밀번호 로그인**: 설정한 `APP_PASSWORD` 입력 시 주인장(Master) 권한으로 로그인 (저장된 API 키 사용).
- **게스트 로그인**: 친구가 자신의 API 키(`AIza...`)를 입력하면 게스트(Guest) 권한으로 로그인.

### 3. 실행하기 (Run Locally)
```bash
streamlit run src/app.py
```

## 📱 배포 및 모바일 사용 (Deployment)
이 앱을 스마트폰이나 다른 컴퓨터에서 사용하고 싶으신가요?
자세한 방법은 [DEPLOYMENT.md](./DEPLOYMENT.md) 문서를 참고하세요.

## 🛠 기술 스택 (Tech Stack)
- **Language**: Python
- **Web Framework**: Streamlit
- **AI Model**: Google Gemini 3.0 Pro (gemini-3-pro-preview)
- **Libraries**: OpenPyXL (Excel), Pydantic (Data Model)
