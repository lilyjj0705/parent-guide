# -*- coding: utf-8 -*-
"""
「부모, 학부모가 되다」 AI 도우미 — Streamlit + Gemini
경기도교육청 2026 신입생 학부모 안내서 기반 챗봇

과제2: 과제1의 키워드 검색 에이전트를 Python(Streamlit) 웹앱으로 구현
- 좌측 사이드바: 옵션(핵심 키워드 / 카테고리 / 답변 길이)
- 중앙: 챗봇 인터페이스
- 책 본문에서 관련 섹션을 찾아(검색) Gemini에게 근거로 전달 → 책 기반 답변
"""

import os
import json

# 이 app.py가 있는 폴더를 기준으로 이미지 경로를 잡는다
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import re
import streamlit as st
import google.generativeai as genai

# ─────────────────────────────────────────────
# 1. 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="부모, 학부모가 되다 — AI 도우미",
    page_icon="📘",
    layout="wide",
)

# 동의어 사전: 학부모 일상어 → 책 용어
SYNONYMS = {
    "왕따": "학교폭력", "따돌림": "학교폭력", "괴롭힘": "학교폭력",
    "휴대폰": "스마트폰 과의존", "핸드폰": "스마트폰 과의존", "폰": "스마트폰 과의존",
    "게임중독": "스마트폰 과의존", "유튜브": "스마트폰 과의존",
    "밥": "식습관", "편식": "식습관", "급식": "급식예절", "안먹": "식습관",
    "책읽기": "독서 습관", "독서": "독서 습관",
    "친구": "친구 관계", "사귀": "친구 관계", "외톨이": "친구 관계",
    "한글": "한글책임교육", "읽기": "한글책임교육", "글자": "한글책임교육",
    "체험학습": "학교장허가 교외체험학습", "가족여행": "학교장허가 교외체험학습",
    "결석": "출결", "지각": "출결", "아파서": "출결", "병가": "출결",
    "돌봄": "늘봄학교", "방과후": "늘봄학교",
    "상담": "학부모 상담", "면담": "학부모 상담",
    "준비물": "학교생활 기초", "입학준비": "학교생활 기초",
    "화내": "감정표현", "짜증": "감정표현", "우는": "감정표현",
    "거짓말": "거짓말 지도",
    "잠": "생활 습관", "수면": "생활 습관", "늦잠": "생활 습관",
    "예방주사": "예방접종", "주사": "예방접종", "백신": "예방접종",
    "우울": "마음 건강", "불안": "마음 건강", "스트레스": "마음 건강",
    "사이버": "사이버폭력", "온라인": "디지털 시민성", "인터넷": "디지털 시민성",
    "성교육": "성폭력", "성범죄": "디지털 성범죄",
    "학대": "아동학대", "방임": "아동학대",
    "공부": "스스로 공부", "집중못": "집중", "산만": "집중",
    "교육과정": "1학년 교육과정", "수업내용": "1학년 교육과정",
    "진로": "진로연계교육", "꿈": "진로연계교육",
    "난독": "난독증", "다문화": "다문화교육",
    "안전": "교통안전", "교통": "교통안전",
    "자존감": "부모 자존감", "교육관": "자녀 교육관",
    "소통": "공감적 의사소통", "대화": "밥상머리 대화",
    "기질": "아이 성향과 기질", "성향": "아이 성향과 기질",
    "양치": "이 닦기", "치아": "이 닦기", "손씻기": "손 씻기",
    "정리": "정리정돈", "청소": "정리정돈",
}


# ─────────────────────────────────────────────
# 2. 데이터 로드 (캐시)
# ─────────────────────────────────────────────
@st.cache_data
def load_book():
    with open("book_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


BOOK = load_book()
SECTIONS = BOOK["sections"]
KEYWORDS = BOOK["keywords"]
CATEGORIES = ["전체"] + sorted({s["category"] for s in SECTIONS})


# ─────────────────────────────────────────────
# 3. 검색 엔진 (동의어 확장 + 점수화)
# ─────────────────────────────────────────────
def search_sections(query, category="전체", top_k=4):
    query = (query or "").strip().lower()
    if not query:
        return []

    terms = query.split()
    expanded = list(terms)
    for t in terms:
        for key, mapped in SYNONYMS.items():
            if key in t and mapped.lower() not in expanded:
                expanded.append(mapped.lower())

    scored = []
    for sec in SECTIONS:
        if category != "전체" and sec["category"] != category:
            continue
        body = sec["body"].lower()
        score = 0
        for t in expanded:
            if not t:
                continue
            score += body.count(t)
            if t in sec["sub"].lower():
                score += 8
            if t in sec["unit"].lower():
                score += 4
        if score > 0:
            scored.append((score, sec))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]]


# ─────────────────────────────────────────────
# 4. Gemini 설정
# ─────────────────────────────────────────────
# 구글이 모델 이름을 자주 바꾸므로, 여러 후보를 순서대로 시도해
# 현재 키에서 실제로 작동하는 모델을 자동으로 선택한다.
CANDIDATE_MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash-latest",
    "gemini-pro-latest",
]


@st.cache_resource
def get_model():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None
    genai.configure(api_key=api_key)

    # 1) 후보 목록을 위에서부터 시도
    for name in CANDIDATE_MODELS:
        try:
            m = genai.GenerativeModel(name)
            m.generate_content("ping")  # 실제 호출로 사용 가능 여부 확인
            return m
        except Exception:
            continue

    # 2) 후보가 모두 실패하면, 키에서 사용 가능한 모델을 직접 조회
    try:
        for info in genai.list_models():
            if "generateContent" in getattr(info, "supported_generation_methods", []):
                short = info.name.split("/")[-1]
                if "flash" in short or "pro" in short:
                    try:
                        m = genai.GenerativeModel(short)
                        m.generate_content("ping")
                        return m
                    except Exception:
                        continue
    except Exception:
        pass

    return None


def build_prompt(question, found, length_opt):
    if found:
        context = "\n\n".join(
            f"[{s['unit']} > {s['sub']} (p.{s['page']})]\n{s['body'][:1500]}"
            for s in found
        )
    else:
        context = "(관련 내용을 책에서 찾지 못했습니다.)"

    length_rule = {
        "간단히": "3~4문장으로 핵심만 답하세요.",
        "보통": "5~8문장으로 친절하게 설명하세요.",
        "자세히": "구체적인 예시와 함께 자세히 안내하세요.",
    }[length_opt]

    return f"""당신은 경기도교육청 『부모, 학부모가 되다』 안내서를 바탕으로
초등 신입생 학부모의 질문에 답하는 따뜻한 상담 도우미입니다.

[규칙]
- 아래 '책 내용'에 근거해서만 답하세요. 책에 없는 내용은 추측하지 말고
  "안내서에는 해당 내용이 자세히 나와 있지 않습니다"라고 안내하세요.
- 학부모가 안심할 수 있도록 친절하고 따뜻한 존댓말로 답하세요.
- {length_rule}
- 답변 끝에 참고한 섹션과 페이지를 "📖 참고: ..." 형식으로 표시하세요.

[책 내용]
{context}

[학부모 질문]
{question}
"""


# ─────────────────────────────────────────────
# 5. 사이드바 (옵션)
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📘 안내서 도우미")
    st.caption("경기도교육청 2026 신입생 학부모 안내서 기반")

    st.divider()
    category = st.selectbox("📂 분야 선택", CATEGORIES)
    length_opt = st.radio("✏️ 답변 길이", ["간단히", "보통", "자세히"], index=1)

    st.divider()
    st.markdown("**⭐ 핵심 키워드** (눌러서 질문)")
    cols = st.columns(2)
    for i, kw in enumerate(KEYWORDS[:24]):
        if cols[i % 2].button(kw, key=f"kw_{i}", use_container_width=True):
            st.session_state["pending"] = f"{kw}에 대해 알려주세요."

    with st.expander("키워드 더 보기"):
        for i, kw in enumerate(KEYWORDS[24:], start=24):
            if st.button(kw, key=f"kw_{i}", use_container_width=True):
                st.session_state["pending"] = f"{kw}에 대해 알려주세요."

    st.divider()
    if st.button("🗑️ 대화 비우기", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()


# ─────────────────────────────────────────────
# 6. 중앙 — 챗봇 인터페이스
# ─────────────────────────────────────────────
st.title("📘 부모, 학부모가 되다 — AI 도우미")
st.caption("초등 입학을 앞둔 학부모님, 궁금한 점을 편하게 물어보세요. 안내서 내용을 바탕으로 답해드립니다.")

model = get_model()
if model is None:
    st.error(
        "⚠️ Gemini API 키가 설정되지 않았습니다.\n\n"
        "Streamlit Cloud의 **Settings > Secrets**에 아래처럼 입력하세요:\n\n"
        '```\nGEMINI_API_KEY = "여기에_본인_키"\n```'
    )

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 지난 대화 표시
for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# 사이드바 키워드 클릭 → 대기 중인 질문 처리
pending = st.session_state.pop("pending", None)
user_input = st.chat_input("예) 급식을 잘 안 먹어요 / 학교폭력 / 늘봄학교가 뭔가요?")
question = user_input or pending

if question:
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if model is None:
            answer = "API 키가 설정되지 않아 답변할 수 없습니다. 사이드바 위 안내를 확인해 주세요."
            st.markdown(answer)
        else:
            found = search_sections(question, category)
            with st.spinner("안내서를 찾아보는 중..."):
                try:
                    prompt = build_prompt(question, found, length_opt)
                    resp = model.generate_content(prompt)
                    answer = resp.text
                except Exception as e:
                    answer = f"답변 생성 중 오류가 발생했습니다: {e}"
            st.markdown(answer)
            if found:
                with st.expander("📖 참고한 안내서 원문·삽화 보기", expanded=True):
                    for s in found:
                        st.markdown(f"**{s['unit']} > {s['sub']}** (p.{s['page']})")
                        imgs = s.get("images", [])
                        valid, missing = [], []
                        for p in imgs:
                            fp = os.path.join(BASE_DIR, p)
                            if os.path.exists(fp):
                                valid.append(fp)
                            else:
                                missing.append(p)
                        if valid:
                            st.image(valid, use_container_width=True)
                        if missing:
                            st.caption("⚠️ 이미지 파일을 찾지 못함: " + ", ".join(missing))
                        st.caption(s["body"][:400] + " …")
                        st.divider()

    st.session_state["messages"].append({"role": "assistant", "content": answer})
