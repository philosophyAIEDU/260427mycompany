# 🎙️ 개인용 AI 회의록 팀 (Local Gemma 4)

Gemma 4 멀티모달(오디오) 모델을 로컬 환경(Ollama)에서 활용하여 기밀 회의 내용도 외부 유출 없이 안전하게 전사, 요약, 그리고 Action Item 도출까지 자동으로 수행하는 Streamlit 웹 애플리케이션입니다.

Alex(전사), Mia(분석), Chris(실행 가이드) 3인의 에이전트 체제를 통해 완벽한 회의록을 작성하고, 결과를 Slack 및 Notion으로 즉시 공유/아카이빙할 수 있습니다.

---

## 🚀 시작하기

### 1. 패키지 설치
이 앱은 Python과 Streamlit 환경에서 동작합니다. 아래 명령어로 필요한 패키지를 설치하세요.
```bash
pip install -r requirements.txt
```

*(참고: 오디오 파일 처리를 위해 시스템에 `ffmpeg`가 설치되어 있어야 합니다. Windows의 경우 `choco install ffmpeg` 또는 `winget install ffmpeg`를 사용하세요.)*

### 2. 앱 실행
설치가 완료되면 앱을 실행합니다.
```bash
streamlit run app.py
```
브라우저에서 `http://localhost:8501`로 접속하면 앱을 이용할 수 있습니다.

---

## 📲 외부 서비스 연동 가이드

회의 분석 결과를 팀 메신저나 지식 저장소로 자동 전송하려면, 사이드바의 **[⚙️ 설정]** 탭에서 연동 정보를 입력해야 합니다.

### 1. Slack 연동 가이드
Chris(에이전트)가 정리한 핵심 요약 메시지를 Slack 채널로 전송합니다.

**발급 방법:**
1. [Slack API 페이지 (api.slack.com)](https://api.slack.com/apps)에 접속하여 `Create New App`을 클릭합니다.
2. `From scratch`를 선택하고, 앱 이름과 연동할 워크스페이스를 지정합니다.
3. 좌측 메뉴의 **OAuth & Permissions**로 이동합니다.
4. **Scopes** 항목 중 **Bot Token Scopes**에 `chat:write` 권한을 추가합니다.
5. 페이지 상단의 **Install to Workspace** 버튼을 눌러 앱을 워크스페이스에 설치합니다.
6. 발급된 `Bot User OAuth Token` (보통 `xoxb-`로 시작)을 복사합니다.

**앱 설정:**
* 앱 사이드바 **[Slack 연동 설정]** 탭에 복사한 토큰을 입력합니다.
* 메시지를 보낼 채널명 (예: `#general` 또는 `C12345678`)을 입력합니다. (단, 해당 채널에 방금 만든 봇을 초대해야 합니다: `/invite @봇이름`)

### 2. Notion 연동 가이드
최종 회의록 전체(Action Item 포함)를 팀 Notion 데이터베이스에 영구 보관합니다.

**발급 방법:**
1. [Notion Developers 페이지 (www.notion.so/my-integrations)](https://www.notion.so/my-integrations)에 접속합니다.
2. **새 통합(New integration)** 버튼을 클릭하고 이름을 지정한 뒤 저장합니다.
3. 발급된 **프라이빗 API 통합 토큰 (Internal Integration Secret)**을 복사합니다.
4. 회의록을 저장할 Notion 페이지(데이터베이스/표 형식 권장)를 엽니다.
5. 우측 상단의 `...` (더보기) -> **연결(Connections)** -> **연결 추가**를 클릭하고 방금 생성한 통합 이름을 검색해 추가합니다.
6. 해당 데이터베이스 페이지의 URL(`https://www.notion.so/workspace/데이터베이스ID?v=...`)에서 **Database ID**(보통 32자리 영문/숫자)를 복사합니다.

**앱 설정:**
* 앱 사이드바 **[Notion 연동 설정]** 탭에 토큰(Integration Secret)과 Database ID를 입력합니다.

---

## 💡 VRAM 최적화 가이드 (Ollama - Gemma 4)
오디오 분석은 많은 메모리(VRAM)를 소모합니다. 쾌적한 로컬 구동을 위해 다음을 권장합니다.

1. **양자화 모델 사용**: `gemma4:e4b-q4_K_M` 처럼 4-bit 양자화된 모델을 사용하세요.
2. **오디오 분할 (Chunking)**: 긴 회의는 한 번에 전사하기 어렵습니다. 앱 내부에 10분 단위로 오디오를 잘라 순차적으로 분석하는 로직(`split_audio`)이 적용되어 있으니 긴 오디오 파일도 안심하고 업로드하세요.
3. **컨텍스트 제한**: 모델 호출 시 문맥 길이(`num_ctx`)를 적절히 조절하여 OOM(Out Of Memory)을 방지할 수 있습니다.
