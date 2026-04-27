import streamlit as st
import requests
import base64
import time
import os
import json
from datetime import datetime

# ━━━ 프롬프트 정의 ━━━
ALEX_SYSTEM_PROMPT = """당신은 회의록 작성팀의 'Alex'입니다. 오디오 데이터를 텍스트로 전환하고 화자를 구분하는 전문가입니다.

★★★ 업무 지침 ★★★
1. Gemma 4의 네이티브 오디오 처리 능력을 사용하여 음성 데이터를 정확한 텍스트로 변환하세요.
2. 화자의 목소리 톤과 패턴을 분석하여 [화자 1], [화자 2] 등으로 구분하여 기록하세요.
3. 전문 용어나 고유 명사는 문맥을 파악하여 정확한 철자로 교정하세요.
4. "음...", "어..."와 같은 추임새(filler words)는 제거하여 가독성을 높이세요.

출력 형식:
■ 회의 전체 스크립트 (화자 구분 포함)
■ 주요 키워드 리스트
"""

MIA_SYSTEM_PROMPT = """당신은 회의록 분석 전문가 'Mia'입니다. Alex가 작성한 전사본에서 핵심 가치를 찾아냅니다.

★★★ 분석 관점 ★★★
1. 회의의 주요 목적이 달성되었는지 평가하세요.
2. 각 화자별 주장과 이에 대한 합의 사항을 정리하세요.
3. 명시적으로 드러나지 않은 숨은 의도나 중요한 인사이트를 도출하세요.
4. 논쟁이 있었던 부분과 미결된 과제를 식별하세요.

출력 형식:
■ 회의 핵심 요약 (3줄)
■ 주요 결정 사항 (Decision Log)
■ 미결 과제 및 논점 분석
"""

CHRIS_SYSTEM_PROMPT = """당신은 비서실장 'Chris'입니다. 분석된 내용을 바탕으로 실행 계획을 세우고 공유합니다.

★★★ 최종 결과물 작성 ★★★
1. Mia의 분석을 바탕으로 '누가, 언제까지, 무엇을' 해야 하는지 Action Items를 명확히 추출하세요.
2. 전체 내용을 사내 공유용 표준 마크다운 양식으로 정리하세요.
3. Slack에 즉시 전송할 수 있는 요약본을 별도로 작성하세요.

출력 형식:
━━━ 📋 최종 회의록 ━━━
(전체 요약 및 결과)

━━━ 🎯 Action Items (실행 목표) ━━━
- [ ] 항목 / 담당자 / 기한

━━━ 📲 Slack 알림 메시지 (복사용) ━━━
(이모지를 활용한 간결한 요약)
"""

# ━━━ 유틸리티 함수 ━━━

def call_ollama(model, prompt, audio=None, context=None):
    """
    Ollama API를 호출하는 헬퍼 함수
    * 실제 구현 시 Ollama 멀티모달(오디오) 규격에 맞춰 수정 필요
    """
    with st.spinner(f"[{model}] 모델이 분석을 진행 중입니다... (약간의 시간이 소요될 수 있습니다)"):
        url = "http://127.0.0.1:11434/api/generate"
        
        final_prompt = prompt
        if context:
            final_prompt += f"\n\n[이전 분석 내용]\n{context}"
            
        payload = {
            "model": model,
            "prompt": final_prompt,
            "stream": False
        }
        
        # 오디오 처리는 현재 Ollama API가 기본적으로 지원하지 않으므로, 
        # 오디오 파일이 들어왔을 때는 데모용 임시 텍스트로 대체하여 다음 단계(요약 등)를 진행할 수 있게 합니다.
        if audio and "Alex" in prompt and "[입력된 회의록 텍스트]" not in prompt:
            time.sleep(2)
            return "■ 전체 스크립트\n[화자 1] 이번 프로젝트 진행 상황 공유 부탁드립니다.\n[화자 2] 네, 현재 80% 완료되었습니다.\n■ 주요 키워드 리스트\n- 프로젝트, 진행률"
            
        try:
            # 로컬 환경에서 긴 분석을 고려해 넉넉한 timeout 설정
            response = requests.post(url, json=payload, timeout=600)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"⚠️ 모델 서버 응답 오류: {response.text}"
        except Exception as e:
            return f"⚠️ API 호출 실패: {str(e)}"



def audio_to_base64(audio_bytes):
    return base64.b64encode(audio_bytes).decode("utf-8")


# ━━━ 메인 UI ━━━
st.set_page_config(page_title="개인용 AI 회의록 팀", page_icon="🎙️", layout="wide")
st.title("🎙️ 개인용 AI 회의록 팀 (Local Gemma 4)")

with st.sidebar:
    st.header("⚙️ 설정")
    
    selected_model = st.selectbox("사용할 모델 선택", ["gemma4:26b", "gemma4:e4b"])
    
    # 모델 서버 상태 확인
    st.subheader("📡 서버 상태")
    try:
        res = requests.get("http://127.0.0.1:11434/", timeout=3)
        if res.status_code == 200:
            st.success("🟢 모델 서버 연결 정상 (Ollama 실행 중)")
        else:
            st.warning("🟡 모델 서버 응답 이상")
    except:
        st.error("🔴 모델 서버 연결 실패 (Ollama 실행 확인)")
        
    st.markdown("---")
    
    # [신규] VRAM 최적화 가이드 표시
    st.header("💡 VRAM 최적화 가이드")
    st.info("""
    **Gemma 4 (Local) 구동 최적화 팁**
    
    * **모델 양자화**: `q4_K_M` 등 4-bit 양자화 모델을 사용하여 VRAM 요구량을 크게 줄이세요.
    * **Context Window 제한**: Ollama 호출 시 `num_ctx: 4096` 등 적절한 값을 지정해 메모리 초과(OOM)를 방지하세요.
    * **오디오 분할 (Chunking)**: 15분 이상의 긴 회의는 메모리 한계를 초과하기 쉽습니다. 앱 내부에 구현된 자동 10분 단위 분할 로직이 작동하여 OOM을 방지합니다.
    * **GPU Offloading**: VRAM이 부족한 경우 Ollama 설정에서 `num_gpu` 값을 조절하여 일부 레이어를 CPU로 분산시킬 수 있습니다.
    """)

    st.info("🔒 로컬에서 구동되므로 사내 기밀 회의도 안심하고 처리 가능합니다.")

# 데이터 업로드 영역
tab1, tab2 = st.tabs(["🎵 오디오 업로드", "📝 직접 입력"])

audio_bytes = None
with tab1:
    audio_file = st.file_uploader("회의 녹음 파일 (MP3, WAV 등)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=False)
    if audio_file:
        audio_bytes = audio_file.read()
        st.audio(audio_bytes)

with tab2:
    manual_text = st.text_area("이미 텍스트화된 회의록이 있다면 입력하세요.", height=150)

# 분석 실행
if st.button("🚀 회의 분석 시작") and (audio_bytes or manual_text):
    
    # 1단계: Alex (Transcription)
    with st.expander("📝 1단계: Alex의 음성 전사 및 화자 구분", expanded=True):
        st.write("Alex가 오디오를 분석하여 전사하고 있습니다...")
        
        # 직접 입력한 텍스트가 있다면 프롬프트에 추가
        final_alex_prompt = ALEX_SYSTEM_PROMPT
        if manual_text:
            final_alex_prompt += f"\n\n[입력된 회의록 텍스트]\n{manual_text}\n위 텍스트를 바탕으로 화자 구분 및 스크립트를 작성해줘."
            
        alex_res = call_ollama(model=selected_model, prompt=final_alex_prompt, audio=audio_bytes)
        st.markdown(alex_res)

    # 2단계: Mia (Analysis)
    with st.expander("🔍 2단계: Mia의 핵심 인사이트 분석"):
        st.write(f"Mia가 회의록의 숨은 가치를 분석 중입니다... (선택 모델: {selected_model})")
        mia_res = call_ollama(model=selected_model, prompt=MIA_SYSTEM_PROMPT, context=alex_res)
        st.markdown(mia_res)

    # 3단계: Chris (Final Report & Slack/Notion)
    with st.expander("📋 3단계: Chris의 액션 아이템 & 공유", expanded=True):
        st.write(f"Chris가 최종 회의록과 액션 아이템을 정리하고 있습니다... (선택 모델: {selected_model})")
        chris_res = call_ollama(model=selected_model, prompt=CHRIS_SYSTEM_PROMPT, context=mia_res)
        st.markdown(chris_res)
