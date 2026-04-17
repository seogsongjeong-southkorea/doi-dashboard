# -*- coding: utf-8 -*-
"""
Research Impact Dashboard
- DOI 여러 개를 한 번에 입력
- OpenAlex + Crossref로 무료 메타데이터/피인용 수 조회
- 자동 분야 분류 + 분야별 기여도
- 총합 / 분야별 추정 상위 %
- 분야별 대표 연구 설명 자동 생성
- SQLite로 저장. 다음 날 DOI 몇 개만 추가해도 자동 업데이트.
"""

import io
import json
import math
import re
import sqlite3
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ======================================================================
# PAGE CONFIG (반드시 모든 st.* 호출보다 먼저 와야 함)
# ======================================================================
st.set_page_config(
    page_title="Research Impact",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ======================================================================
# 커스텀 CSS
# ======================================================================
CUSTOM_CSS = """
<style>
  /* 전체 배경 */
  .stApp {
      background:
        radial-gradient(1200px 600px at 10% -10%, rgba(123,47,247,0.18), transparent 60%),
        radial-gradient(1000px 600px at 100% 0%, rgba(0,212,255,0.12), transparent 60%),
        linear-gradient(180deg, #0a0e1f 0%, #0a0e1f 100%);
  }
  /* Streamlit 기본 UI 정리 */
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {background: transparent;}
  .block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1400px;}

  /* 타이포 */
  h1, h2, h3, h4 { font-family: "Inter","Pretendard",system-ui,sans-serif; letter-spacing: -0.01em;}
  h1 {
      font-weight: 800; font-size: 2.4rem;
      background: linear-gradient(90deg,#00d4ff 0%, #a07bff 60%, #ff6bb0 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      margin-bottom: 0.2rem;
  }
  .subtitle {color:#8892b8; font-size:0.98rem; margin-bottom: 1.6rem;}

  /* KPI 카드 */
  .kpi-grid {display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px;}
  .kpi {
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px; padding: 18px 20px;
      backdrop-filter: blur(6px);
      transition: border-color .2s ease, transform .2s ease;
  }
  .kpi:hover {border-color: rgba(0,212,255,0.45); transform: translateY(-2px);}
  .kpi .label {color:#8892b8; font-size: 0.78rem; font-weight:600; text-transform: uppercase; letter-spacing: .08em;}
  .kpi .value {color:#fff; font-size: 2rem; font-weight: 800; line-height:1.15; margin-top: 6px;}
  .kpi .sub   {color:#8fa2d9; font-size: 0.82rem; margin-top: 6px;}

  /* 랭킹 카드 */
  .rank-wrap {display:grid; grid-template-columns: 1fr 1fr; gap:14px;}
  .rank {
      position: relative; overflow: hidden;
      border-radius: 18px; padding: 22px 22px;
      border: 1px solid rgba(255,255,255,0.08);
      background:
         linear-gradient(135deg, rgba(0,212,255,0.08), rgba(123,47,247,0.08)),
         rgba(255,255,255,0.02);
  }
  .rank.domestic::before, .rank.global::before{
      content:""; position:absolute; inset:0;
      background: radial-gradient(400px 200px at 0% 0%, rgba(0,212,255,0.18), transparent 60%);
      pointer-events:none;
  }
  .rank.global::before{
      background: radial-gradient(400px 200px at 100% 0%, rgba(255,107,176,0.18), transparent 60%);
  }
  .rank .tag {color:#9fb2e5; font-size:.82rem; font-weight:600; text-transform: uppercase; letter-spacing:.12em;}
  .rank .main {color:#fff; font-size: 2.6rem; font-weight: 800; margin-top:4px;}
  .rank .desc {color:#9fb2e5; font-size:.92rem; margin-top: 8px;}

  /* 필드 카드 */
  .field {
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px; padding: 18px 20px; margin-bottom: 14px;
  }
  .field .fhead {display:flex; justify-content:space-between; align-items:center;}
  .field .fname {font-size: 1.15rem; font-weight: 700; color:#fff;}
  .field .fmini {display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;}
  .chip {
      display:inline-block; padding: 4px 10px; border-radius: 999px;
      font-size: .78rem; font-weight:600;
  }
  .field .fdesc {color:#cfd8f2; font-size: .95rem; line-height: 1.55; margin-top: 10px;}
  .bar-outer {background: rgba(255,255,255,0.06); height: 8px; border-radius: 4px; overflow:hidden; margin-top:12px;}
  .bar-inner {height:100%; border-radius: 4px;}

  /* 버튼 */
  .stButton > button, .stDownloadButton > button {
      background: linear-gradient(90deg,#00d4ff 0%, #7b2ff7 100%);
      color: #fff; border: 0;
      border-radius: 10px; padding: 0.55rem 1.2rem;
      font-weight: 700; letter-spacing:.01em;
      transition: transform .15s ease, box-shadow .15s ease;
  }
  .stButton > button:hover, .stDownloadButton > button:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 25px rgba(123,47,247,0.35);
  }
  .stButton > button[kind="secondary"] {
      background: rgba(255,255,255,0.06); color:#cfd8f2;
      border:1px solid rgba(255,255,255,0.12);
  }

  /* Textarea */
  .stTextArea textarea {
      background: rgba(255,255,255,0.03) !important;
      color: #e6ecff !important;
      border: 1px solid rgba(255,255,255,0.10) !important;
      border-radius: 12px !important;
      font-family: "JetBrains Mono","SF Mono", ui-monospace, monospace !important;
      font-size: 0.92rem !important;
  }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {gap:8px;}
  .stTabs [data-baseweb="tab"] {
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 10px; padding: 6px 14px; color:#9fb2e5;
  }
  .stTabs [aria-selected="true"] {
      background: linear-gradient(90deg, rgba(0,212,255,.14), rgba(123,47,247,.14));
      color: #fff !important; border-color: rgba(0,212,255,0.35);
  }

  /* 테이블 */
  [data-testid="stDataFrame"] {border-radius: 12px; overflow:hidden;}

  .hint {color:#7d8ab4; font-size:.82rem;}
  .small {color:#8fa2d9; font-size:.82rem;}
  hr.soft {border:none; border-top:1px solid rgba(255,255,255,0.06); margin: 1rem 0;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ======================================================================
# 상수 / 설정
# ======================================================================
DB_PATH = "papers.db"
CURRENT_YEAR = datetime.now().year
OPENALEX = "https://api.openalex.org"
CROSSREF = "https://api.crossref.org"
USER_AGENT = "ResearchImpactDashboard/1.0 (https://streamlit.app)"

# 분야 카테고리. 필요하면 여기서 자유롭게 수정 가능.
CATEGORIES = {
    "Liver / MASLD": {
        "color": "#00d4ff",
        "keywords": ["masld", "nafld", "fatty liver", "steatotic", "hepatitis",
                     "hepatic", "liver", "cirrhosis", "fibrosis", "hepatocellular",
                     "hcc", "nash"],
        "template": "간질환 분야({label}): MASLD, 간섬유화, 간경변, 간암 등을 주제로 {n}편의 연구를 통해 질병 부담·위험요인·예후를 정량화.",
    },
    "Cardiovascular": {
        "color": "#ff6bb0",
        "keywords": ["atrial fibrillation", "heart failure", "cardiovascular",
                     "coronary", "stroke", "hypertension", "cardiac", "myocardial",
                     "cardiomyopathy", "ischemic"],
        "template": "심혈관 분야({label}): 심방세동, 심부전, 관상동맥질환 등 심혈관 질환과 예후를 다룬 {n}편의 연구.",
    },
    "Metabolic / Diabetes": {
        "color": "#a07bff",
        "keywords": ["diabetes", "insulin", "obesity", "metabolic syndrome",
                     "glycemic", "hyperglycemia", "bmi", "adipose", "type 2 diabetes"],
        "template": "대사질환 분야({label}): 당뇨병, 비만, 대사증후군 등 대사 위험요인과 합병증을 규명한 {n}편의 연구.",
    },
    "Cancer / Oncology": {
        "color": "#ffa647",
        "keywords": ["cancer", "carcinoma", "tumor", "oncology", "malignan",
                     "neoplasm", "chemotherapy", "metastasis"],
        "template": "종양학 분야({label}): 암 발생, 예후, 치료 등을 다룬 {n}편의 연구.",
    },
    "AI / Prediction": {
        "color": "#00ffa3",
        "keywords": ["machine learning", "deep learning", "artificial intelligence",
                     "prediction model", "neural network", "algorithm",
                     "predictive model", "risk score", "xgboost", "random forest"],
        "template": "의료 AI/예측모형 분야({label}): 머신러닝·예측모형 기반 임상 의사결정 지원 연구 {n}편.",
    },
    "Big Data / Epidemiology": {
        "color": "#ff5eec",
        "keywords": ["cohort", "epidemiolog", "nationwide", "population-based",
                     "national database", "claims data", "registry", "burden",
                     "incidence", "prevalence", "korean national"],
        "template": "빅데이터 역학 분야({label}): 국가 코호트·대규모 DB 기반 질병부담 및 역학적 근거를 생산한 {n}편의 연구.",
    },
    "Review / Guideline": {
        "color": "#c3ff47",
        "keywords": ["review", "meta-analysis", "systematic review", "guideline",
                     "consensus", "recommendation", "position statement"],
        "template": "리뷰/가이드라인 분야({label}): 체계적 문헌고찰·메타분석·가이드라인 등 임상 근거를 체계화한 {n}편.",
    },
    "Methodology / Causal": {
        "color": "#47d4ff",
        "keywords": ["causal inference", "mendelian randomization", "propensity",
                     "instrumental variable", "methodology", "statistical method",
                     "simulation study"],
        "template": "방법론 분야({label}): 인과추론·멘델리안 무작위화 등 연구 설계의 엄밀성을 강화한 {n}편의 연구.",
    },
}
UNCAT_COLOR = "#8fa2d9"

# 추정 벤치마크 (내부 비교용, 완벽한 공식값 아님)
GLOBAL_BM = {
    "citations": [(99, 10000), (95, 3000), (90, 1500), (75, 500), (50, 100), (25, 30), (10, 10)],
    "papers":    [(99, 200),   (95, 100),  (90, 60),   (75, 30),  (50, 15),  (25, 7),  (10, 3)],
    "h_index":   [(99, 50),    (95, 30),   (90, 20),   (75, 12),  (50, 7),   (25, 4),  (10, 2)],
}
DOMESTIC_BM = {
    "citations": [(99, 5000), (95, 1500), (90, 700),  (75, 200), (50, 50),  (25, 15), (10, 5)],
    "papers":    [(99, 150),  (95, 80),   (90, 50),   (75, 25),  (50, 10),  (25, 5),  (10, 2)],
    "h_index":   [(99, 40),   (95, 25),   (90, 16),   (75, 9),   (50, 5),   (25, 3),  (10, 2)],
}
FIELD_GLOBAL_BM = {
    "citations":  [(99, 2000), (95, 700),  (90, 300),  (75, 100), (50, 30), (25, 10), (10, 3)],
    "papers":     [(99, 50),   (95, 25),   (90, 15),   (75, 8),   (50, 4),  (25, 2),  (10, 1)],
    "h_index":    [(99, 20),   (95, 12),   (90, 8),    (75, 5),   (50, 3),  (25, 2),  (10, 1)],
}
FIELD_DOMESTIC_BM = {
    "citations":  [(99, 1000), (95, 400),  (90, 180),  (75, 70),  (50, 20), (25, 7),  (10, 2)],
    "papers":     [(99, 40),   (95, 20),   (90, 12),   (75, 6),   (50, 3),  (25, 2),  (10, 1)],
    "h_index":    [(99, 15),   (95, 9),    (90, 6),    (75, 4),   (50, 2),  (25, 1),  (10, 1)],
}

# 대표 고영향 저널 (무료 버전에서 "최상위 저널" 카운트 용도. 공식 IF 아님)
TOP_TIER_JOURNALS = {
    "new england journal of medicine", "the new england journal of medicine",
    "lancet", "the lancet", "nature", "science", "cell", "jama",
    "the bmj", "bmj", "nature medicine", "nature genetics", "nature biotechnology",
    "nature communications", "circulation", "european heart journal",
    "journal of hepatology", "hepatology", "gastroenterology", "gut",
    "journal of clinical oncology", "jama internal medicine", "jama cardiology",
    "jama oncology", "lancet oncology", "lancet diabetes & endocrinology",
    "lancet gastroenterology & hepatology", "annals of internal medicine",
    "diabetes care", "european heart journal",
}

# ======================================================================
# DB
# ======================================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            doi TEXT PRIMARY KEY,
            title TEXT, journal TEXT, publisher TEXT, year INTEGER,
            abstract TEXT, cited_by INTEGER DEFAULT 0, authors TEXT,
            is_oa INTEGER DEFAULT 0, oa_url TEXT,
            openalex_id TEXT, openalex_topics TEXT,
            primary_category TEXT, secondary_category TEXT,
            contribution_score REAL DEFAULT 0,
            last_updated TEXT, source TEXT
        )
    """)
    conn.commit()
    conn.close()

def upsert_paper(p):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO papers
        (doi,title,journal,publisher,year,abstract,cited_by,authors,is_oa,oa_url,
         openalex_id,openalex_topics,primary_category,secondary_category,
         contribution_score,last_updated,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        (p.get("doi") or "").lower(),
        p.get("title") or "",
        p.get("journal") or "",
        p.get("publisher") or "",
        p.get("year"),
        p.get("abstract") or "",
        int(p.get("cited_by") or 0),
        p.get("authors") or "",
        int(bool(p.get("is_oa"))),
        p.get("oa_url") or "",
        p.get("openalex_id") or "",
        json.dumps(p.get("openalex_topics") or []),
        p.get("primary_category") or "Uncategorized",
        p.get("secondary_category") or "",
        float(p.get("contribution_score") or 0),
        datetime.now().isoformat(timespec="seconds"),
        p.get("source") or "openalex",
    ))
    conn.commit()
    conn.close()

def load_papers():
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM papers", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def existing_dois():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT doi FROM papers").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()
    finally:
        conn.close()

def delete_one(doi):
    conn = get_conn()
    conn.execute("DELETE FROM papers WHERE doi = ?", (doi.lower(),))
    conn.commit()
    conn.close()

def clear_db():
    conn = get_conn()
    conn.execute("DELETE FROM papers")
    conn.commit()
    conn.close()

# ======================================================================
# DOI 파싱 / 외부 API
# ======================================================================
def clean_doi(s):
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^doi:\s*", "", s, flags=re.IGNORECASE)
    return s.strip().strip(".,;()[]'\"")

def parse_doi_list(text):
    if not text:
        return []
    items = re.split(r"[\n,;\s]+", text.strip())
    out = []
    seen = set()
    for item in items:
        d = clean_doi(item)
        if not d or "/" not in d or len(d) < 7:
            continue
        k = d.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out

def reconstruct_abstract(inv_index):
    if not inv_index:
        return ""
    positions = {}
    for word, poss in inv_index.items():
        for p in poss:
            positions[p] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions.keys()))

def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s

def fetch_openalex(doi, session=None):
    s = session or _session()
    try:
        url = f"{OPENALEX}/works/https://doi.org/{doi}"
        r = s.get(url, timeout=25)
        if r.status_code != 200:
            return None
        d = r.json()
        pl = d.get("primary_location") or {}
        src = pl.get("source") or {}
        journal = src.get("display_name") or ""
        publisher = src.get("host_organization_name") or ""
        is_oa = bool(pl.get("is_oa"))
        oa_url = pl.get("pdf_url") or pl.get("landing_page_url") or ""
        topics = []
        for t in (d.get("topics") or [])[:5]:
            topics.append({
                "name": t.get("display_name", "") or "",
                "field": ((t.get("field") or {}).get("display_name") or ""),
                "subfield": ((t.get("subfield") or {}).get("display_name") or ""),
                "score": t.get("score", 0) or 0,
            })
        authors = []
        for a in (d.get("authorships") or []):
            nm = ((a.get("author") or {}).get("display_name") or "").strip()
            if nm:
                authors.append(nm)
        return {
            "doi": doi,
            "title": d.get("title") or d.get("display_name") or "",
            "journal": journal,
            "publisher": publisher,
            "year": d.get("publication_year"),
            "abstract": reconstruct_abstract(d.get("abstract_inverted_index")),
            "cited_by": int(d.get("cited_by_count") or 0),
            "authors": "; ".join(authors),
            "is_oa": is_oa,
            "oa_url": oa_url,
            "openalex_id": d.get("id") or "",
            "openalex_topics": topics,
            "source": "openalex",
        }
    except Exception:
        return None

def fetch_crossref(doi, session=None):
    s = session or _session()
    try:
        r = s.get(f"{CROSSREF}/works/{doi}", timeout=25)
        if r.status_code != 200:
            return None
        d = (r.json() or {}).get("message") or {}
        title = (d.get("title") or [""])[0] or ""
        journal = (d.get("container-title") or [""])[0] or ""
        publisher = d.get("publisher") or ""
        year = None
        dp = (d.get("issued") or {}).get("date-parts")
        if dp and isinstance(dp, list) and dp and dp[0]:
            try:
                year = int(dp[0][0])
            except Exception:
                year = None
        authors = []
        for a in (d.get("author") or []):
            nm = f"{a.get('given','')} {a.get('family','')}".strip()
            if nm:
                authors.append(nm)
        return {
            "doi": doi,
            "title": title,
            "journal": journal,
            "publisher": publisher,
            "year": year,
            "abstract": d.get("abstract") or "",
            "cited_by": int(d.get("is-referenced-by-count") or 0),
            "authors": "; ".join(authors),
            "is_oa": False,
            "oa_url": "",
            "openalex_id": "",
            "openalex_topics": [],
            "source": "crossref",
        }
    except Exception:
        return None

def fetch_paper(doi, session=None):
    p = fetch_openalex(doi, session)
    if p and (p.get("title") or p.get("journal")):
        return p
    p2 = fetch_crossref(doi, session)
    if p2:
        return p2
    return None

# ======================================================================
# 분류 / 점수 / 랭킹
# ======================================================================
def classify(paper):
    text_parts = [
        (paper.get("title") or ""),
        (paper.get("abstract") or ""),
        (paper.get("journal") or ""),
    ]
    topics = paper.get("openalex_topics") or []
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except Exception:
            topics = []
    for t in topics:
        text_parts.append(t.get("name", "") or "")
        text_parts.append(t.get("field", "") or "")
        text_parts.append(t.get("subfield", "") or "")
    text = " ".join(text_parts).lower()

    scores = {}
    for cat, info in CATEGORIES.items():
        s = 0
        for kw in info["keywords"]:
            if kw in text:
                s += text.count(kw)
        scores[cat] = s
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    if not ranked or ranked[0][1] == 0:
        return ("Uncategorized", "")
    primary = ranked[0][0]
    secondary = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else ""
    return (primary, secondary)

def contribution_score(cited_by, year):
    cited = int(cited_by or 0)
    try:
        yr = int(year) if year else CURRENT_YEAR
    except Exception:
        yr = CURRENT_YEAR
    age = max(1, CURRENT_YEAR - yr + 1)
    base = math.log(1 + cited)
    if age <= 3:
        rec = 1.20
    elif age <= 7:
        rec = 1.00
    else:
        rec = 0.85
    return round(base * rec, 3)

def compute_h_index(citations):
    s = sorted([int(x or 0) for x in citations], reverse=True)
    h = 0
    for i, c in enumerate(s):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h

def top_percent(value, benchmarks):
    """value가 top X% 안에 드는지 추정. benchmarks: [(percentile, threshold), ...]"""
    for pct, th in benchmarks:
        if value >= th:
            return 100 - pct  # pct=99 이면 top 1%
    return None  # top 90% 바깥

def estimate_rank(citations, papers_n, h, bm_set_global, bm_set_domestic):
    def combine(B):
        a = top_percent(citations, B["citations"])
        b = top_percent(papers_n, B["papers"])
        c = top_percent(h, B["h_index"])
        weights = {"c": 0.5, "p": 0.2, "h": 0.3}
        num = 0.0
        den = 0.0
        for key, v in [("c", a), ("p", b), ("h", c)]:
            if v is not None:
                num += v * weights[key]
                den += weights[key]
        if den == 0:
            return None
        return round(num / den, 1)
    return {"domestic": combine(bm_set_domestic), "global": combine(bm_set_global)}

def rank_label(pct):
    if pct is None:
        return "상위 10% 바깥 (추정)"
    if pct <= 1:
        return "상위 1% 추정"
    if pct <= 5:
        return f"상위 {pct}% 추정"
    if pct <= 10:
        return f"상위 {pct}% 추정"
    return f"상위 {pct}% 추정"

def development_stage(n_papers, total_cites, recent3_papers, recent3_cites):
    """매우 단순한 발전단계 추정"""
    if n_papers <= 2:
        return ("초기 단계", "논문 수가 적음. 주제 형성 단계.")
    if n_papers >= 15 and total_cites >= 300:
        if recent3_papers >= 5 and recent3_cites >= 100:
            return ("주도 단계", "논문 수·누적 영향력·최근 생산성이 모두 높음.")
        return ("핵심 기여 단계", "누적 영향력이 상당하며 대표작이 분명.")
    if recent3_papers >= max(3, n_papers * 0.4):
        return ("성장 단계", "최근 생산성과 관심이 빠르게 증가 중.")
    return ("성숙 단계", "꾸준한 기여를 이어가는 단계.")

# ======================================================================
# 배치 처리
# ======================================================================
def process_dois(dois, only_new=False, progress_cb=None, status_cb=None):
    """DOI 리스트를 처리. only_new=True면 DB에 없는 DOI만."""
    existing = existing_dois() if only_new else set()
    target = [d for d in dois if d.lower() not in existing]
    skipped = len(dois) - len(target)

    session = _session()
    succ, fail = 0, 0
    failed = []

    total = len(target)
    for i, doi in enumerate(target, start=1):
        if status_cb:
            status_cb(f"({i}/{total}) {doi} 조회 중...")
        p = fetch_paper(doi, session=session)
        if not p:
            fail += 1
            failed.append(doi)
        else:
            primary, secondary = classify(p)
            p["primary_category"] = primary
            p["secondary_category"] = secondary
            p["contribution_score"] = contribution_score(p.get("cited_by"), p.get("year"))
            upsert_paper(p)
            succ += 1
        if progress_cb:
            progress_cb(i / max(1, total))
        # OpenAlex/Crossref 공손함을 위해 살짝 쉼
        time.sleep(0.12)

    return {"success": succ, "failed": fail, "skipped": skipped, "failed_dois": failed}

def recompute_all():
    df = load_papers()
    if df.empty:
        return 0
    for _, row in df.iterrows():
        p = row.to_dict()
        # openalex_topics 복원
        try:
            p["openalex_topics"] = json.loads(p.get("openalex_topics") or "[]")
        except Exception:
            p["openalex_topics"] = []
        primary, secondary = classify(p)
        p["primary_category"] = primary
        p["secondary_category"] = secondary
        p["contribution_score"] = contribution_score(p.get("cited_by"), p.get("year"))
        upsert_paper(p)
    return len(df)

# ======================================================================
# UI 컴포넌트
# ======================================================================
def render_header():
    st.markdown("<h1>◆ Research Impact</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>DOI만 붙여넣으면 무료 공개 데이터(OpenAlex · Crossref)로 "
        "당신의 연구 지형과 추정 임팩트를 시각화합니다.</div>",
        unsafe_allow_html=True,
    )

def render_input_section():
    st.markdown("#### DOI 입력")
    st.markdown(
        "<div class='hint'>한 줄에 하나씩 붙여넣거나 쉼표로 구분하세요. "
        "이미 추가한 DOI는 자동으로 건너뜁니다.</div>",
        unsafe_allow_html=True,
    )
    text = st.text_area(
        label="DOI",
        key="doi_input",
        label_visibility="collapsed",
        placeholder="예:\n10.1016/j.jhep.2025.01.001\n10.1038/s41575-025-00001-x\n10.1001/jama.2024.12345",
        height=180,
    )
    c1, c2, c3, c4 = st.columns([1.1, 1.1, 1, 3])
    with c1:
        btn_add = st.button("➕ 새 DOI 추가", use_container_width=True)
    with c2:
        btn_refresh = st.button("🔄 전체 인용수 갱신", use_container_width=True,
                                help="이미 저장된 모든 논문의 피인용 수/메타데이터를 다시 조회합니다. 느립니다.")
    with c3:
        btn_recalc = st.button("🧠 재계산", use_container_width=True,
                               help="저장된 데이터로 분류·점수·랭킹만 다시 계산합니다. 빠릅니다.")
    return text, btn_add, btn_refresh, btn_recalc

def kpi_cards(items):
    html = "<div class='kpi-grid'>"
    for label, value, sub, color in items:
        sub_html = f"<div class='sub'>{sub}</div>" if sub else ""
        html += (
            f"<div class='kpi'>"
            f"<div class='label'>{label}</div>"
            f"<div class='value' style='color:{color};'>{value}</div>"
            f"{sub_html}"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_overview(df):
    n = len(df)
    total_cites = int(df["cited_by"].fillna(0).sum()) if n else 0
    years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int) if n else pd.Series([], dtype=int)
    recent3 = int((years >= CURRENT_YEAR - 2).sum()) if len(years) else 0
    cats = df["primary_category"].fillna("Uncategorized") if n else pd.Series([], dtype=str)
    n_fields = int((cats != "Uncategorized").nunique()) if n else 0
    h = compute_h_index(df["cited_by"].fillna(0).tolist()) if n else 0

    top_tier_n = 0
    if n:
        jlower = df["journal"].fillna("").str.lower()
        top_tier_n = int(jlower.isin(TOP_TIER_JOURNALS).sum())

    oa_n = int(df["is_oa"].fillna(0).sum()) if n else 0

    kpi_cards([
        ("총 논문", f"{n:,}", "누적", "#ffffff"),
        ("총 피인용", f"{total_cites:,}", f"논문당 평균 {round(total_cites/n,1) if n else 0}", "#00d4ff"),
        ("h-index (추정)", f"{h}", "OpenAlex/Crossref 기반", "#a07bff"),
        ("최근 3년 논문", f"{recent3}", f"{CURRENT_YEAR-2}–{CURRENT_YEAR}", "#ff6bb0"),
        ("활동 분야", f"{n_fields}", "자동 분류 기준", "#00ffa3"),
        ("최상위 저널", f"{top_tier_n}", "Nature·Lancet·JAMA 등", "#ffa647"),
        ("오픈액세스", f"{oa_n}", "OpenAlex is_oa", "#47d4ff"),
    ])

    # 총합 랭킹
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("#### 총합 추정 랭킹")
    st.markdown("<div class='small'>내부 규칙 기반 추정 백분위입니다. 공식 등수 아님.</div>",
                unsafe_allow_html=True)

    rank = estimate_rank(total_cites, n, h, GLOBAL_BM, DOMESTIC_BM)
    dom_pct = rank["domestic"]; glb_pct = rank["global"]
    dom_txt = rank_label(dom_pct); glb_txt = rank_label(glb_pct)

    st.markdown(
        f"""
        <div class="rank-wrap">
            <div class="rank domestic">
                <div class="tag">🇰🇷 국내 추정</div>
                <div class="main">{dom_txt}</div>
                <div class="desc">논문 수 · 총 피인용 · h-index를 가중 결합한 추정 백분위</div>
            </div>
            <div class="rank global">
                <div class="tag">🌐 글로벌 추정</div>
                <div class="main">{glb_txt}</div>
                <div class="desc">같은 지표로 글로벌 벤치마크와 비교한 추정 백분위</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if n:
        st.markdown("<br/>", unsafe_allow_html=True)
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.markdown("#### 연도별 논문 · 피인용")
            ydf = df.copy()
            ydf["year"] = pd.to_numeric(ydf["year"], errors="coerce")
            ydf = ydf.dropna(subset=["year"])
            ydf["year"] = ydf["year"].astype(int)
            by_year = ydf.groupby("year").agg(
                papers=("doi", "count"),
                citations=("cited_by", "sum"),
            ).reset_index()
            if len(by_year):
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=by_year["year"], y=by_year["papers"],
                    name="논문 수", marker_color="#00d4ff",
                    yaxis="y1", opacity=0.85,
                ))
                fig.add_trace(go.Scatter(
                    x=by_year["year"], y=by_year["citations"],
                    name="피인용 합", mode="lines+markers",
                    line=dict(color="#ff6bb0", width=3),
                    yaxis="y2",
                ))
                fig.update_layout(
                    height=340, margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#cfd8f2"),
                    yaxis=dict(title="논문 수", gridcolor="rgba(255,255,255,0.06)"),
                    yaxis2=dict(title="피인용 합", overlaying="y", side="right",
                                gridcolor="rgba(255,255,255,0)"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                )
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### 분야 구성")
            cat_counts = df["primary_category"].fillna("Uncategorized").value_counts().reset_index()
            cat_counts.columns = ["category", "count"]
            colors = [CATEGORIES.get(c, {}).get("color", UNCAT_COLOR) for c in cat_counts["category"]]
            fig = go.Figure(go.Pie(
                labels=cat_counts["category"],
                values=cat_counts["count"],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0a0e1f", width=2)),
                textinfo="label+percent",
            ))
            fig.update_layout(
                height=340, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#cfd8f2"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

def render_by_field(df):
    if df.empty:
        st.info("논문이 없습니다.")
        return

    st.markdown("#### 분야별 기여도 · 추정 랭킹")
    st.markdown(
        "<div class='small'>각 분야에 대해 그 분야의 논문만 따로 모아 벤치마크와 비교한 추정 백분위를 계산합니다.</div>",
        unsafe_allow_html=True,
    )

    # 분야별 최대값 구해서 시각적 상대 바 계산
    cats = sorted(df["primary_category"].fillna("Uncategorized").unique().tolist())
    # 계산 결과 모으기
    rows = []
    for cat in cats:
        sub = df[df["primary_category"].fillna("Uncategorized") == cat]
        n_sub = len(sub)
        cites_sub = int(sub["cited_by"].fillna(0).sum())
        h_sub = compute_h_index(sub["cited_by"].fillna(0).tolist())
        contrib = float(sub["contribution_score"].fillna(0).sum())
        years_sub = pd.to_numeric(sub["year"], errors="coerce").dropna().astype(int)
        recent3 = int((years_sub >= CURRENT_YEAR - 2).sum()) if len(years_sub) else 0
        recent3_cites = int(sub.loc[pd.to_numeric(sub["year"], errors="coerce") >= CURRENT_YEAR - 2, "cited_by"]
                            .fillna(0).sum()) if n_sub else 0
        rank = estimate_rank(cites_sub, n_sub, h_sub, FIELD_GLOBAL_BM, FIELD_DOMESTIC_BM)
        stage, stage_desc = development_stage(n_sub, cites_sub, recent3, recent3_cites)
        rows.append({
            "category": cat,
            "n": n_sub,
            "citations": cites_sub,
            "h": h_sub,
            "contrib": contrib,
            "recent3": recent3,
            "recent3_cites": recent3_cites,
            "dom_pct": rank["domestic"],
            "glb_pct": rank["global"],
            "stage": stage,
            "stage_desc": stage_desc,
        })
    if not rows:
        return

    max_contrib = max(r["contrib"] for r in rows) or 1.0
    # 기여도 내림차순
    rows.sort(key=lambda r: -r["contrib"])

    for r in rows:
        cat = r["category"]
        info = CATEGORIES.get(cat)
        color = info["color"] if info else UNCAT_COLOR
        # 대표 논문 2편
        sub = df[df["primary_category"].fillna("Uncategorized") == cat]
        top_papers = sub.sort_values("cited_by", ascending=False).head(2)
        reps_html = ""
        for _, p in top_papers.iterrows():
            title = (p.get("title") or "").strip()
            if not title:
                continue
            journal = (p.get("journal") or "").strip()
            yr = p.get("year")
            cb = int(p.get("cited_by") or 0)
            yr_str = f" ({int(yr)})" if pd.notnull(yr) else ""
            reps_html += f"<div class='small' style='margin-top:6px;'>• {title}{yr_str} — <em>{journal}</em> · 인용 {cb}</div>"

        # 설명 템플릿
        template = info["template"] if info else "{label} 관련 {n}편의 연구."
        journals_in_cat = sub["journal"].fillna("").unique().tolist()[:3]
        journals_str = ", ".join([j for j in journals_in_cat if j]) or "다양한 학술지"
        desc = template.format(n=r["n"], label=cat, journals=journals_str)

        # 바 너비
        bar_w = int(round(100 * r["contrib"] / max_contrib))

        dom_txt = rank_label(r["dom_pct"])
        glb_txt = rank_label(r["glb_pct"])

        st.markdown(
            f"""
            <div class="field">
                <div class="fhead">
                    <div class="fname">{cat}</div>
                    <span class="chip" style="background:{color}22;border:1px solid {color}55;color:{color};">
                        {r['stage']}
                    </span>
                </div>
                <div class="fmini">
                    <span class="chip" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#cfd8f2;">논문 {r['n']}편</span>
                    <span class="chip" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#cfd8f2;">피인용 {r['citations']:,}</span>
                    <span class="chip" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#cfd8f2;">h {r['h']}</span>
                    <span class="chip" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#cfd8f2;">기여점수 {round(r['contrib'],2)}</span>
                    <span class="chip" style="background:rgba(0,212,255,0.10);border:1px solid rgba(0,212,255,0.35);color:#7ce7ff;">🇰🇷 {dom_txt}</span>
                    <span class="chip" style="background:rgba(255,107,176,0.10);border:1px solid rgba(255,107,176,0.35);color:#ffb6d8;">🌐 {glb_txt}</span>
                </div>
                <div class="bar-outer"><div class="bar-inner" style="width:{bar_w}%;background:linear-gradient(90deg,{color}88,{color});"></div></div>
                <div class="fdesc">{desc} <span style="color:#9fb2e5;">— {r['stage_desc']}</span></div>
                {reps_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_papers_table(df):
    if df.empty:
        st.info("논문이 없습니다.")
        return

    st.markdown("#### 전체 논문 목록")
    # 필터
    with st.container():
        c1, c2, c3 = st.columns([1.2, 1.2, 2])
        with c1:
            cats_all = ["전체"] + sorted(df["primary_category"].fillna("Uncategorized").unique().tolist())
            cat_pick = st.selectbox("분야", cats_all, index=0)
        with c2:
            year_vals = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
            if len(year_vals):
                y_min, y_max = int(year_vals.min()), int(year_vals.max())
            else:
                y_min, y_max = CURRENT_YEAR - 10, CURRENT_YEAR
            if y_min == y_max:
                year_pick = (y_min, y_max)
                st.caption(f"연도: {y_min}")
            else:
                year_pick = st.slider("연도 범위", min_value=y_min, max_value=y_max,
                                      value=(y_min, y_max))
        with c3:
            q = st.text_input("제목/저널/DOI 검색", placeholder="키워드")

    d = df.copy()
    if cat_pick != "전체":
        d = d[d["primary_category"].fillna("Uncategorized") == cat_pick]
    d["year_num"] = pd.to_numeric(d["year"], errors="coerce")
    d = d[(d["year_num"].isna()) | ((d["year_num"] >= year_pick[0]) & (d["year_num"] <= year_pick[1]))]
    if q:
        ql = q.lower()
        mask = (
            d["title"].fillna("").str.lower().str.contains(ql)
            | d["journal"].fillna("").str.lower().str.contains(ql)
            | d["doi"].fillna("").str.lower().str.contains(ql)
        )
        d = d[mask]

    d = d.sort_values(["cited_by", "year"], ascending=[False, False])

    show = d[[
        "doi", "title", "journal", "year", "cited_by",
        "primary_category", "secondary_category", "contribution_score", "is_oa"
    ]].rename(columns={
        "doi": "DOI", "title": "제목", "journal": "저널", "year": "연도",
        "cited_by": "피인용", "primary_category": "주 분야",
        "secondary_category": "부 분야", "contribution_score": "기여점수",
        "is_oa": "OA",
    })
    show["OA"] = show["OA"].map({1: "●", 0: ""})
    st.dataframe(show, use_container_width=True, height=480)

    st.markdown("##### 개별 삭제")
    del_doi = st.text_input("삭제할 DOI", key="del_doi")
    if st.button("🗑 해당 DOI 삭제"):
        if del_doi.strip():
            delete_one(clean_doi(del_doi))
            st.success(f"삭제됨: {del_doi}")
            st.rerun()

    csv_bytes = d.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ CSV로 내려받기",
        csv_bytes,
        file_name=f"papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

def render_backup(df):
    st.markdown("#### 백업 / 복원")
    st.markdown(
        "<div class='hint'>Streamlit Community Cloud는 앱이 오랜 시간 멈춰 있으면 데이터가 사라질 수 있습니다. "
        "가끔 JSON 백업을 내려받아 두세요. 재시작 후엔 업로드해 복원하면 됩니다.</div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if len(df):
            data = df.to_dict(orient="records")
            payload = json.dumps({"exported_at": datetime.now().isoformat(), "papers": data}, ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ JSON 백업 내려받기",
                payload.encode("utf-8"),
                file_name=f"research_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("내려받을 데이터가 없습니다.")
    with c2:
        up = st.file_uploader("JSON 백업 업로드", type=["json"])
        if up is not None:
            try:
                obj = json.loads(up.read().decode("utf-8"))
                recs = obj.get("papers") if isinstance(obj, dict) else obj
                if not isinstance(recs, list):
                    st.error("형식이 맞지 않습니다.")
                else:
                    cnt = 0
                    for r in recs:
                        # openalex_topics 문자열이면 그대로 통과
                        try:
                            topics = r.get("openalex_topics")
                            if isinstance(topics, str):
                                r["openalex_topics"] = json.loads(topics or "[]")
                        except Exception:
                            r["openalex_topics"] = []
                        upsert_paper(r)
                        cnt += 1
                    st.success(f"{cnt}건 복원 완료.")
                    st.rerun()
            except Exception as e:
                st.error(f"업로드 실패: {e}")

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
    st.markdown("##### 위험 구역")
    if st.button("🧨 저장된 모든 논문 삭제", type="secondary"):
        st.session_state["confirm_clear"] = True
    if st.session_state.get("confirm_clear"):
        st.warning("정말 모두 삭제할까요? 되돌릴 수 없습니다.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("네, 삭제합니다"):
                clear_db()
                st.session_state["confirm_clear"] = False
                st.success("삭제되었습니다.")
                st.rerun()
        with cc2:
            if st.button("취소"):
                st.session_state["confirm_clear"] = False
                st.rerun()

# ======================================================================
# MAIN
# ======================================================================
def main():
    init_db()
    render_header()

    # 입력
    with st.container():
        text, btn_add, btn_refresh, btn_recalc = render_input_section()

    # 액션 처리
    if btn_add:
        dois = parse_doi_list(text)
        if not dois:
            st.warning("유효한 DOI가 없습니다.")
        else:
            ph_status = st.empty()
            ph_bar = st.progress(0.0)
            result = process_dois(
                dois, only_new=True,
                progress_cb=lambda v: ph_bar.progress(min(1.0, v)),
                status_cb=lambda s: ph_status.info(s),
            )
            ph_bar.empty()
            ph_status.empty()
            st.success(
                f"완료 · 추가 {result['success']}건 / 실패 {result['failed']}건 / 이미 존재 {result['skipped']}건"
            )
            if result["failed_dois"]:
                with st.expander(f"실패한 DOI {len(result['failed_dois'])}개 보기"):
                    st.code("\n".join(result["failed_dois"]))

    if btn_refresh:
        df_now = load_papers()
        if df_now.empty:
            st.info("갱신할 데이터가 없습니다.")
        else:
            all_dois = df_now["doi"].tolist()
            ph_status = st.empty()
            ph_bar = st.progress(0.0)
            result = process_dois(
                all_dois, only_new=False,
                progress_cb=lambda v: ph_bar.progress(min(1.0, v)),
                status_cb=lambda s: ph_status.info(s),
            )
            ph_bar.empty(); ph_status.empty()
            st.success(f"전체 갱신 완료 · 성공 {result['success']}건 / 실패 {result['failed']}건")

    if btn_recalc:
        n = recompute_all()
        st.success(f"{n}건 재계산 완료.")

    df = load_papers()

    if df.empty:
        st.markdown("<br/>", unsafe_allow_html=True)
        st.info(
            "아직 저장된 논문이 없습니다. 위에 DOI를 붙여넣고 **새 DOI 추가**를 눌러주세요. "
            "한 번에 수백 개도 가능합니다."
        )
        return

    # 탭
    tab1, tab2, tab3, tab4 = st.tabs(["📊 전체 요약", "🧭 분야별", "📚 논문 목록", "💾 백업"])
    with tab1:
        render_overview(df)
    with tab2:
        render_by_field(df)
    with tab3:
        render_papers_table(df)
    with tab4:
        render_backup(df)

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='hint'>데이터원: OpenAlex, Crossref · 랭킹은 내부 규칙 기반 추정 백분위 · "
        f"마지막 새로고침: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
