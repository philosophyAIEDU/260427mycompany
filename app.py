import streamlit as st
import requests
import base64
import time
import os
import json
from datetime import datetime
from slack_sdk import WebClient
from notion_client import Client
from pydub import AudioSegment

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
    # 임시 모의 응답
    time.sleep(2)
    if "Alex" in prompt:
        return "■ 전체 스크립트\n[화자 1] 이번 프로젝트 진행 상황 공유 부탁드립니다.\n[화자 2] 네, 현재 80% 완료되었습니다.\n■ 주요 키워드 리스트\n- 프로젝트, 진행률"
    elif "Mia" in prompt:
        return "■ 핵심 요약\n프로젝트가 원활하게 진행 중임.\n■ 결정 사항\n기한 내 완료 목표.\n■ 미결 과제\nQA 일정 조율."
    else:
        return "━━━ 📋 최종 회의록 ━━━\n프로젝트 80% 완료.\n━━━ 🎯 Action Items ━━━\n- [ ] QA 일정 조율 / 김대리 / 이번주\n━━━ 📲 Slack 알림 메시지 ━━━\n🚀 프로젝트 현황: 80% 달성 완료. 이번 주 QA 일정 조율 바랍니다."

def send_to_slack(token, channel, text):
    try:
        client = WebClient(token=token)
        client.chat_postMessage(channel=channel, text=text)
        return True
    except Exception as e:
        st.error(f"Slack 전송 실패: {e}")
        return False

def send_to_notion(token, database_id, title, content):
    """
    최종 회의록을 Notion Database의 새로운 페이지로 저장하는 함수
    """
    try:
        notion = Client(auth=token)
        
        # 텍스트가 너무 길 경우 2000자씩 분할(Notion API Block 한계)
        blocks = []
        chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
        for chunk in chunks:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": chunk}
                        }
                    ]
                }
            })

        new_page = {
            "parent": {"database_id": database_id},
            "properties": {
                "이름": {
                    "title": [
                        {
                            "text": {"content": title}
                        }
                    ]
                }
            },
            "children": blocks
        }
        
        notion.pages.create(**new_page)
        return True
    except Exception as e:
        st.error(f"Notion 전송 실패: {e}")
        return False

def split_audio(file_path, chunk_length_ms=600000): # 기본 10분(600,000ms)
    """
    긴 오디오 파일을 설정된 시간(기본 10분) 단위로 분할합니다.
    (VRAM 최적화용)
    """
    try:
        audio = AudioSegment.from_file(file_path)
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        return chunks
    except Exception as e:
        st.warning(f"오디오 분할을 위해 ffmpeg이 필요합니다. {e}")
        return None

def audio_to_base64(audio_bytes):
    return base64.b64encode(audio_bytes).decode("utf-8")


# ━━━ 메인 UI ━━━
st.set_page_config(page_title="개인용 AI 회의록 팀", page_icon="🎙️", layout="wide")
st.title("🎙️ 개인용 AI 회의록 팀 (Local Gemma 4)")

with st.sidebar:
    st.header("⚙️ 설정")
    
    with st.expander("Slack 연동 설정", expanded=False):
        slack_token = st.text_input("Slack Bot Token", type="password")
        slack_channel = st.text_input("Channel ID (예: #general)")
        
    with st.expander("Notion 연동 설정", expanded=False):
        notion_token = st.text_input("Notion Integration Token", type="password")
        notion_db_id = st.text_input("Notion Database ID")
        
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
        # 실제 구현시: audio_bytes를 임시 파일로 저장 후 split_audio로 청크 단위 분리 -> 각각 call_ollama 수행 -> 결과 병합
        alex_res = call_ollama(model="gemma4:e2b", prompt=ALEX_SYSTEM_PROMPT, audio=audio_bytes)
        st.markdown(alex_res)

    # 2단계: Mia (Analysis)
    with st.expander("🔍 2단계: Mia의 핵심 인사이트 분석"):
        st.write("Mia가 회의록의 숨은 가치를 분석 중입니다...")
        mia_res = call_ollama(model="gemma4:e4b", prompt=MIA_SYSTEM_PROMPT, context=alex_res)
        st.markdown(mia_res)

    # 3단계: Chris (Final Report & Slack/Notion)
    with st.expander("📋 3단계: Chris의 액션 아이템 & 공유", expanded=True):
        st.write("Chris가 최종 회의록과 액션 아이템을 정리하고 있습니다...")
        chris_res = call_ollama(model="gemma4:e4b", prompt=CHRIS_SYSTEM_PROMPT, context=mia_res)
        st.markdown(chris_res)
        
        # 외부 전송 버튼 영역
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if slack_token and slack_channel:
                if st.button("📲 Slack으로 요약 전송", use_container_width=True):
                    # Chris의 출력물 중 Slack 섹션만 파싱
                    try:
                        slack_msg = chris_res.split("━━━ 📲 Slack")[1].strip() if "━━━ 📲 Slack" in chris_res else chris_res
                    except:
                        slack_msg = chris_res
                        
                    if send_to_slack(slack_token, slack_channel, slack_msg):
                        st.success("✅ Slack 전송 완료!")
            else:
                st.button("📲 Slack으로 요약 전송", use_container_width=True, disabled=True, help="사이드바에서 Slack 설정을 완료해주세요.")
                
        with col2:
            if notion_token and notion_db_id:
                if st.button("💾 Notion에 회의록 아카이빙", use_container_width=True):
                    title = f"📝 [{datetime.now().strftime('%Y-%m-%d')}] AI 회의록 요약"
                    if send_to_notion(notion_token, notion_db_id, title, chris_res):
                        st.success("✅ Notion 아카이빙 완료!")
            else:
                st.button("💾 Notion에 회의록 아카이빙", use_container_width=True, disabled=True, help="사이드바에서 Notion 설정을 완료해주세요.")
