# 📘 부모, 학부모가 되다 — AI 도우미

경기도교육청 『부모, 학부모가 되다』(2026 신입생 학부모 안내서)를 바탕으로
초등 입학 학부모의 질문에 답하는 Gemini 기반 Streamlit 챗봇입니다.

## 기능
- 자연어 질문 → 안내서 관련 섹션 자동 검색(동의어 확장 포함) → Gemini가 책 근거로 답변
- 사이드바: 핵심 키워드 버튼, 분야 필터, 답변 길이 선택
- 참고한 안내서 원문·페이지 표시

## 로컬 실행
```bash
pip install -r requirements.txt
# .streamlit/secrets.toml.example 를 secrets.toml 로 복사 후 키 입력
streamlit run app.py
```

## 파일 구성
- `app.py` — 메인 앱
- `book_data.json` — 안내서 본문 데이터(23개 섹션)
- `requirements.txt` — 라이브러리 목록
- `.streamlit/secrets.toml.example` — API 키 입력 예시
