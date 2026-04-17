# Research Impact Dashboard

DOI를 여러 개 붙여넣으면 자동으로:
- OpenAlex + Crossref에서 논문 메타데이터·피인용 수 수집
- 자동 분야 분류
- 분야별 기여도 계산
- 총합/분야별 추정 상위 % 계산
- 분야별 대표 연구 설명 생성
- 연도별 트렌드·분야 구성 시각화
- CSV / JSON 내려받기

## 파일 3개
- `app.py` — 앱 본체
- `requirements.txt` — 필요한 라이브러리 목록
- `.streamlit/config.toml` — 테마 설정

## 배포 흐름 (요약)
1. GitHub 계정 가입
2. 새 repo 생성 → 이 파일들을 업로드 (폴더 구조 유지)
3. Streamlit Community Cloud에서 repo 연결 → `app.py`로 배포
4. 생성된 URL에서 DOI 붙여넣기

## 데이터 유지
SQLite(`papers.db`)에 저장됩니다. Streamlit Cloud는 컨테이너가 재생성되면
파일이 사라질 수 있으니, `💾 백업` 탭에서 JSON을 가끔 내려받아 두세요.
다음에 업로드만 하면 복원됩니다.

## 커스터마이즈
`app.py` 상단의 `CATEGORIES` 딕셔너리에서 분야/키워드/설명 템플릿을
자유롭게 수정하세요.
