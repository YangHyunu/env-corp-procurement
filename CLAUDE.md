# CLAUDE.md

> 이 문서는 AI 에이전트(Claude/Cursor 등)가 이 프로젝트에서 작업하기 전에 **가장 먼저 읽어야 하는** 문서입니다.

## 1. 프로젝트 개요

**한국환경공단 환경기초시설 관급자재 SR(사회적 가치) 공급망 분석 및 발주 의사결정 지원 시스템**

### 배경
- 환경공단은 소각·하수처리·바이오 등 시설을 만들 때 다양한 관급자재(펌프·송풍기·약품·계측기 등)를 조달함
- 정부 정책상 사회적 가치 실현(중소·여성·장애인·사회적기업·자활용사촌·창업기업 등)을 일정 비율 이상 달성해야 함
- 같은 세부품명번호를 공급할 수 있는 기업이 수십~수백 곳 → 어떤 SR 군집이 두텁고 신뢰할 만한지 판단이 어려움

### 목표
**발주 실무자가 5분 안에 "이 업체 추천하자" 결정을 내릴 수 있는 의사결정 지원 도구**

### 분석 단위 (PK)
- **세부품명번호(10자리)** × **사업자등록번호(BRN, 10자리)**
- 모든 데이터셋이 이 두 키로 join됨

### 분석 차원
1. **공급망 밀도** — 품목별 유효 SR 보유 업체 수
2. **다중지표 보유** — 한 업체가 여러 SR 보유 (희소성)
3. **낙찰 실적** — 금액·건수·낙찰률
4. **리스크** — 부정당제재 이력
5. **AI 클러스터링** — 다차원 벡터로 유사 업체 군집화

---

## 2. 최종 산출물

| 산출물 | 형태 | 용도 |
|---|---|---|
| 분석 코드 | Python 모듈 + Jupyter 노트북 | 재현·확장 가능한 분석 자산 |
| 분석 결과 보고서 | Markdown / PDF | 의사결정자 보고용 |
| **의사결정 지원 대시보드** | React + FastAPI | **실무자 일상 활용 (핵심)** |

### 대시보드 핵심 기능 (참고 디자인 기반)
- 품목·예산·가중치 입력 → 추천 실행
- KPI 카드: 매칭 업체수 / 공급망 밀도 / 클러스터 수 / 추천 수
- 시각화: DBSCAN 산점도 + 추천 업체 스코어 막대
- 추천 결과 카드: 레이더 차트(5축) + SR 뱃지 + 예상단가 + 낙찰이력
- 클릭 펼침: 제재 이력, 과거 발주 상세, 예상가격 분포

---

## 3. 기술 스택

| 레이어 | 스택 |
|---|---|
| 언어 | **Python 3.12** |
| 데이터 수집 | requests + python-dotenv |
| 패키지 관리 | **uv** (Python 3.12 고정) |
| 워크플로우 | **Airflow** (Dataset 트리거 + Dynamic Task Mapping) |
| 데이터베이스 | **PostgreSQL** |
| 분석 | pandas, scikit-learn, umap-learn, hdbscan, networkx |
| 백엔드 API | **FastAPI** (분석·ML 모델 직접 호출 위해 Python 통일) |
| 프론트엔드 | **React + Vite** (shadcn/ui + Recharts 추정) |
| 시각화(노트북) | matplotlib, plotly |

> **이 표 외 라이브러리는 추가 시 반드시 사용자 확인** (섹션 9 참조)
> "당연히 쓸 거 같으니까" 도 금지 — 모든 신규 의존성은 명시적 합의 필요

---

## 4. 작업 방식

### OMC 사용 규칙

이 프로젝트는 oh-my-claudecode 플러그인을 사용합니다.

#### 에이전트 위임 가이드
- **데이터 분석/클러스터링/통계** → `scientist-high` (Opus)
- **FastAPI 엔드포인트, mart 테이블 로직** → `executor` (Sonnet)
- **PostgreSQL 스키마 설계** → `architect-high` (Opus, 확인 게이트 필수)
- **React 대시보드 컴포넌트** → `designer` + `executor`
- **pipeline/ 수집 모듈** → `executor`
- **변수명 리팩토링, 포맷팅** → Haiku tier

#### 모드 선택
- **MVP 일반 작업**: Autopilot (기본)
- **여러 mart 테이블 동시 빌드, API 엔드포인트 일괄 작성**: Ultrapilot (병렬)
- **토큰 절약 모드 (단순 수정)**: Ecomode
- **노트북 EDA**: 모드 끄고 직접 작업 ("don't autopilot")

#### 게이트 (CLAUDE.md 4번 "확인 필요" 우선)
OMC가 자동으로 진행하더라도, CLAUDE.md 4번에 명시된 "확인 필요" 항목은
사용자 컨펌 없이 진행 금지:
- 새 라이브러리 (uv add 전 확인)
- PostgreSQL 스키마 변경
- AI 모델 선택
- API 엔드포인트 설계
- 분석 모집단 정의

### 큰 결정엔 확인, 사소한 건 디폴트로 진행

#### ✋ 확인이 필요한 것 (멈추고 질문)
- 새 라이브러리·기술 스택 도입
- PostgreSQL 스키마(테이블·컬럼·인덱스) 변경
- AI 모델·알고리즘 선택 (예: DBSCAN vs HDBSCAN, UMAP 차원 수)
- API 엔드포인트 설계 (URL·요청·응답 구조)
- 5개 파일 이상 동시 수정
- 분석 모집단 정의 변경 (필터 조건)

#### ✅ 가정하고 진행 OK (확인 불필요)
- 변수명·함수명·파일명 세부
- 폴더 내 파일 배치
- PEP8 등 표준 코드 스타일
- 기존 함수 시그니처 유지하며 내부 로직 개선
- 로그 메시지·에러 문구
- 테스트 케이스 추가
- 주석·docstring 작성

#### 📝 가정 명시 규칙
디폴트로 진행할 때는 응답 시작에 한 줄 남기세요:
```
가정: numOfRows는 100으로 설정 (G2B 권장값)
```

### 작업 단위
- **계획 → 단계별 실행** 권장
- 큰 작업은 단계로 쪼개고, 각 단계 끝에 짧게 결과만 보고
- 단계마다 일일이 확인받지 말 것 — 전체 계획이 합의됐으면 끝까지 진행 후 한 번에 보고

### AI 모델 도입
**자유롭게 적용하라고 했지만, 후보 2~3개를 제시하고 선택받기** — 결정권은 사용자.

예시:
```
클러스터링 후보:
(a) DBSCAN — 노이즈 분리 강점, eps 튜닝 필요
(b) HDBSCAN — 밀도 다른 군집 자동 처리, 추천
(c) Gaussian Mixture — 확률 출력, 해석 용이
어느 쪽으로 갈까요?
```

---

## 5. 폴더 구조 (현재)

```
project_root/
├── CLAUDE.md                  ← 이 파일 (에이전트 첫 진입점)
├── README.md
├── .env.example / .env / .gitignore
├── pyproject.toml             ← uv 기반 의존성 정의
├── .python-version            ← Python 3.12 고정
│
├── api/                       ← FastAPI
│   ├── main.py                (/api/items, /api/recommend, /api/company, /api/kpi)
│   └── schemas.py
│
├── frontend/                  ← React+Vite+shadcn
│   └── src/{App.tsx, components/, lib/}
│
├── app/                       ← streamlit (deprecated, 정리 예정)
│
├── pipeline/                  ← 수집 + 추천 로직
│   ├── g2b_common.py / g2b_*.py    (14/1/5/9번 수집)
│   ├── procurement_corp.py
│   ├── scoring.py             (v1 룰베이스 — 점진적 deprecate)
│   ├── item_keywords.py       (8개 키워드 → prefix4 + name_regex)
│   ├── ranker.py              (v2 Ranker Protocol — RuleRanker / 향후 LGBMRanker)
│   └── recommend_v2.py        (v2 사전탐색 오케스트레이션)
│
├── scripts/                   ← 학습/적재/마트빌드 진입점
│   ├── ingest_*.py
│   ├── build_features.py / build_stg.py
│   ├── train_baseline.py      (LGBM Classifier)
│   └── train_ranker.py        (LGBM Ranker)
│
├── sql/
├── artifacts/                 ← 학습 산출물 (lgbm_*.txt, metrics.json, feature_importance.csv)
├── docs/                      ← G2B API 명세 + 데이터셋 문서
│   ├── _common.md
│   ├── api/g2b/{14/1/5/9번}.md
│   └── datasets/
├── analysis/
│   ├── notebooks/
│   └── *.html                 ← 분석 보고서, 목업 (dashboard_mockup.html 등)
└── data/raw/                  ← 로컬 raw (gitignore)
```

### 향후 (Phase 2~3)
- `airflow/dags/` — 수집 자동화 본격화 시
- 클라우드 배포 스크립트 — VM 이전 시

---

## 6. 참조 문서 가이드 (이걸 읽어야 할 때)

| 작업 | 먼저 읽어야 할 문서 |
|---|---|
| **G2B API 호출 코드 작성** | `docs/_common.md` + 해당 API 문서 |
| 입찰공고 수집 | `docs/api/g2b/getBidPblancListInfoThngPPSSrch.md` |
| 낙찰자(BRN) 추출 | `docs/api/g2b/getScsbidListSttusThng.md` |
| 개찰결과 / 유찰 분석 | `docs/api/g2b/getOpengResultListInfoThng.md` |
| 복수예가 디테일 | `docs/api/g2b/getOpengResultListInfoThngPreparPcDetail.md` |
| 조달업체 CSV 처리 | `docs/datasets/dataset_procurement_corp.md` |
| BRN 정규화 / 시간 포맷 / 페이징 / 에러 처리 | `docs/_common.md` |

> **`docs/_common.md`는 거의 항상 먼저 읽어야 함** — 모든 G2B 코드 작성의 전제

---

## 7. 핵심 도메인 개념 (필수 이해)

### BRN (사업자등록번호)
- **모든 데이터셋의 통합 조인 키**
- 표준 형태: 하이픈 없는 10자리 숫자 문자열 (`"1408121883"`)
- 국외 업체는 `F` + 9자리 (`"F000000303"`)
- 정규화 함수: `pipeline.g2b_common.normalize_brn`

### 세부품명번호 (`dtilPrdctClsfcNo`)
- 10자리 정수 문자열 (`"4921181901"`)
- 14번 API 응답 + 조달업체 CSV `대표세부품명번호`로 매칭
- pandas로 CSV 로드 시 float로 들어오므로 `f"{int(x):010d}"` 변환 필수

### 한국환경공단 `dminsttCd` (10개)
본사 1 + 권역본부 8 + 사업단 1. 상수: `pipeline.g2b_common.ENV_CORP_DMINSTT_CDS`

### SR (사회적 가치) 인증
- 1차 분류: 조달업체 CSV (3컬럼 Y/N)
- ⚠️ **여성기업인증여부 = 대표자 성별 자동 판별** (인증서 보유 X)
- 진짜 인증서 유효성·만료일은 외부 API(공공구매 인증서 등)로 보강 — 향후 작업

### 분석 파이프라인
```
14번 API (공고 풀, 환경공단 dminsttCd 10개 필터)
   ↓ bidNtceNo
1번 API (낙찰자 BRN)
   ↓ left join (brn)
조달업체 CSV (BRN 마스터 + SR 1차)
   ↓
mart_company_master / mart_company_sr / mart_item_supply
   ↓
FastAPI → React 대시보드
```

---

## 8. 환경 설정

```bash
# uv 설치 (한 번만, 미설치 시)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치 (.venv 자동 생성, Python 3.12)
uv sync

# 분석 단계 진입 시
uv sync --extra analysis
uv sync --extra ml
uv sync --extra api
uv sync --all-extras           # 전부

# 환경변수
cp .env.example .env
# .env 에 G2B_SERVICE_KEY=... 입력

# 동작 확인
uv run python scripts/check_g2b_api.py
```

> **ServiceKey는 본인 보유** — 환경변수 `G2B_SERVICE_KEY`로 통일.
> 운영/개발 키 분리 안 함 (단일 키).
>
> **모든 Python 명령은 `uv run`을 prefix로 사용**하거나 `.venv` 활성화 후 실행.

---

## 9. ⚠️ 절대 하지 말 것

- **ServiceKey 하드코딩 / git commit** — 무조건 `.env`
- **BRN을 정규화 없이 join** — 하이픈/공백 변형 무수히 많음
- **시간 포맷을 한 가지로 가정** — 19/16/10자리 3종 혼재 (`docs/_common.md` 참조)
- **G2B API에 1개월 이상 기간 한 번에 요청** — `INVALID_REQUEST_PARAMETER_ERROR`
- **`bidNtceNo` 명세 size(11/40)대로 잘라서 처리** — 실제 13자리, 명세 신뢰 금지
- **여성기업인증여부=Y를 "인증서 보유"로 해석** — 단순 자동 판별
- **`opengCorpInfo`를 단순 `split("^")`** — 단일/다수/협상 3 케이스 분기 (`parse_openg_corp_info` 사용)
- **새 라이브러리 임의 추가 절대 금지**
  - 사전 합의된 스택(섹션 3) 외 패키지는 코드 작성 전 무조건 사용자 확인
  - `pip install` / `pip3 install` 금지 — pyproject.toml과 어긋남
  - `uv add`도 사용자 확인 후에만 실행
  - "당연히 쓸 거 같으니까" 추가 X — 모든 신규 의존성은 명시적 합의 필요
  - Transitive 의존도 주의 — 한 패키지가 무거운 sub-dependencies 끌어오면 그것도 보고
  - 예외 없음 (분석/시각화/유틸 등 모든 카테고리 동일)
- **PostgreSQL 스키마 임의 변경** — 마이그레이션 + 사용자 확인
- **8개 키워드 외 자연어를 prefix4로 free-text 매핑 시도 금지** — 잘못된 BRN 풀 반환 위험. 매핑은 `pipeline/item_keywords.py` 사전에만 의존
- **calibration 안 된 ML probability를 사용자에게 raw로 노출 금지** — 0.92 같은 숫자는 의미 없고 오해 유발. 운영 카드엔 등급(강추/추천/검토) 또는 순위만
- **공무원 사용자에게 데이터 ingest 트리거 권한 부여 금지** — 권한·책임 분리 원칙. 신선화는 운영팀 책임. 사용자 화면엔 "데이터 기준일" 표기만
- **MVP 단계에서 SR 외부 API 손대기** — v2로 미뤄둠 (현재는 조달업체 CSV의 1차 분류만 사용)

---

## 10. 진행 상황 (2026-05-06)

### 완료
- [x] G2B API 4개 (14/1/5/9번) 수집 + raw 적재
- [x] PostgreSQL 스키마 (`sql/init.sql`, `sql/2026-05-05_*.sql`)
- [x] stg_* / mart_* 마트 빌드 (`build_stg.py`)
- [x] mart_features_at_bid (PIT 피처) — 343,019 rows
- [x] LGBM Classifier 학습 (prefix_warm pool, AUC 0.858, HR@5 41%, SR@5 8.3%)
- [x] LGBM Ranker 비교 학습 (lambdarank)
- [x] FastAPI v1 (`/api/items`, `/api/recommend`, `/api/company`, `/api/kpi`)
- [x] React 대시보드 v0.1 (item_code 단위)
- [x] 사전탐색 모드 v2 목업 (`analysis/dashboard_mockup.html`)
- [x] `pipeline/item_keywords.py` (8개 키워드 → prefix4 + name_regex)

### 진행 중 (사전탐색 모드 — 룰베이스 (A))
- [ ] `pipeline/ranker.py` — Ranker Protocol + RuleRanker (Stage 2 swap point)
- [ ] `pipeline/recommend_v2.py` — retrieve(Stage 1) → rank(Stage 2) → enrich
- [ ] `api/main.py` 엔드포인트 (`/api/v2/recommend`, `/api/v2/keywords`, `/api/v2/meta`)
- [ ] `api/schemas.py` v2 스키마
- [ ] React v2 레이아웃 (입력 폼 + KPI + 카드 6항목 + 시각화 2개)
- [ ] 데이터 기준일 표기 (헤더)

### 향후 (Phase 2 / v3)
- (B) 추천시스템 본격화 — Stage 2를 LGBM 으로 교체 (synthetic bid)
- Stage 1 정교화 — AutoEncoder/Two-Tower BRN 임베딩
- 부정당제재 데이터 소스 확보
- 자동화 Phase 2 (클라우드 VM + crontab)
- streamlit `app/` 정리 (제거 또는 어드민 격리)
- 키워드 free-text 매핑 (8개 제약 해제)

---

## 11. 운영 추천 — 사전탐색 모드 스펙

### 목적
공고 발주 **전** 담당 공무원이 품목·정책 필터·예산을 입력하면 후보 BRN top-K 를 받는다.

### 입력
- 품목 (자연어 키워드 8개) → `pipeline/item_keywords.py` 의 `KEYWORD_FILTERS` dict 매핑
  - 하수처리용 펌프 / 슬러지 탈수기 / 소각로 내화벽돌 / 바이오가스 발전기 /
    수질측정센서 / 대기오염 측정장비 / 폐수처리약품 / 활성탄 필터
- 정책 필터 0~3개 (사회적기업 / 여성기업 / 장애인기업) — hard filter
- 예산 (백만원 단위)

### 키워드 매핑 정책 (다)
- 각 키워드 = `(prefix4_list, name_regex)` 쌍
- 4710 같이 광범위한 prefix4 는 `name_regex` 로 disambiguate (예: 활성탄 vs 슬러지탈수기)
- 매핑 위치: `pipeline/item_keywords.py` (Python dict 하드코딩)
- 갱신: 매핑 수정 = 코드 수정 + 배포 (분기 1회 검토)
- 8개 외 자유입력은 v3 로 미룸

### 아키텍처 — Stage 분리 (확장 포인트)
운영은 단일 함수처럼 동작하지만 내부적으로 Two-Stage 추천 구조:

```
Stage 1 (Retrieve)  →  Stage 2 (Rank)  →  Enrich
키워드+필터로            후보별 점수            카드 정보 채우기
후보 풀 좁히기            (현재 룰베이스)        (예상가/리스크/전례/시각화)
```

`pipeline/ranker.py` 의 `Ranker` Protocol 인터페이스로 Stage 2 교체 가능:
- 현재: `RuleRanker` (4축 가중합)
- 향후 (B): `LGBMRanker` (synthetic bid → predict_proba) — 한 줄 swap

### 출력 (BRN별 카드)
| 항목 | 산출 방식 |
|---|---|
| 예상 가격 (점) | `예산 × BRN 평균 낙찰률`. fallback: 시장 평균 (해당 prefix4) |
| 예상 가격 (구간) | `예산 × BRN 낙찰률 [Q25, Q75]` (n≥3 일 때만 표시) |
| 가격 안정성 | BRN 낙찰률 표준편차 — 낮음(<2pp) / 보통 / 높음(>5pp) |
| 시장 평균 대비 | `(BRN 평균 − 시장 평균)` — "시장보다 +1.1pp 비쌈" |
| 추천 근거 | 룰베이스 reason 템플릿 (낙찰 이력 + 정책 + 권역) |
| 리스크 신호 | 1순위 탈락 이력 (stg_opening_result + stg_award join) + 활동중단 |
| 공급 안정성 | 환경공단 누적 / 최근 1년 / G2B 등록기간 / 제조업 여부 |
| 최근 낙찰 이력 | stg_award TOP 5 |
| 유사 발주 사례 | 같은 prefix4 + 비슷한 예산 발주에서 누가 낙찰됐나 (전례) |
| 시각화 | 해당 BRN 의 낙찰가 분포 / 낙찰률 분포 (히스토그램) |

### 리스크 등급 (4단계)
| 등급 | 조건 |
|---|---|
| 안전 | top1≥3 AND lost=0 |
| 양호 | lost≤2 AND ratio<30% |
| 주의 | lost≥3 OR ratio≥30% OR 최근1년 lost≥2 |
| 미확인 | top1=0 (활동 부족) |

활동중단 레드플래그: 최근 24개월 무낙찰 BRN → "활동 중단 가능성" 경고

### KPI 카드 (의사결정 지원)
- 후보 BRN 수 (시장 깊이: 등록 / 환경공단 활동)
- SR 인증 후보 비율
- 평균 예상 가격
- 공급 위험도
- **계약방식 권장** — 후보 풀 크기 → 1: 수의계약 / 2~5: 제한경쟁 / 6+: 일반경쟁

### 엣지 케이스
- 후보 0건 (필터로 다 제외) → 응답에 "필터 완화 권유" 메시지
- 후보 1건 (단독공급) → 응답에 "단독공급 — 가격경쟁 어려움" 경고
- 키워드 매핑 실패 → 400 에러 + "8개 키워드 중 선택"

### 추천 모드
- **(A) 룰베이스 (현재)**: `pipeline/ranker.RuleRanker` — 4축 가중합
- **(B) LGBM (향후)**: synthetic bid 기반 `LGBMRanker` swap. 응답에 `ml_score` 필드 채워짐 (현재 None)

### 미구현 / 데이터 부재
- 부정당제재 이력 (API 미확보 → 1순위 탈락 이력 + 활동중단으로 대체)
- 진짜 응찰업체 경쟁률 (4개 API 모두 부재 → 시장 깊이 KPI 로 대체)

### 응답 스키마 (v2)
```python
RecommendV2Response:
  item_keyword: str
  matched_prefix4: list[str]
  cutoff_date: str

  kpi: {pool_size, market_depth, sr_count, sr_pct, avg_price, supply_risk, contract_recommend}
  compliance: {sr_obligation_met, sr_in_top5}
  recommendations: [
    {
      rank, brn, corp_name, tier (A/B/C),
      badges: [중소, 부산, 여성기업],
      summary_stats, expected_price, risk, supply_stability,
      recent_awards, precedents, charts,
      rule_score, ml_score: None, score_used: "rule",
      reason
    }
  ]
  meta: {weights_applied, data_freshness_days, ...}
```

---

## 12. 데이터 운영 모델

### 원칙: 공무원은 ingest 를 운영하지 않는다
- 데이터 수집/갱신은 **개발·운영팀 책임**
- 공무원 사용자는 웹 대시보드만 사용
- 대시보드는 "데이터 기준일" 한 줄만 노출 (예: "기준일 2026-04-29")

### 갱신 주기: 주 1회 권장
환경공단 발주 빈도 = 연 612건 ≈ 일 1.7건. 일별 갱신은 운영 부담 ↑ 효용 ↓.
**주 1회 (월요일 새벽 03:00 KST)** 면 의사결정 품질에 영향 거의 없음.

### Raw 적재 (G2B API) — 주간 배치
| API | 호출 윈도 | 의존 | 비고 |
|---|---|---|---|
| 14번 입찰공고 | 지난 14일 (backfill 7일 + 신규 7일) | — | 환경공단 10 dminstt 필터 |
| 1번 낙찰자 | 지난 30일 (늦게 들어오는 낙찰 캐치) | 14번 후 | bidNtceNo 단위 |
| 5번 개찰결과 | 지난 30일 | 14번 후 | winner_brn 추출 |
| 9번 복수예가 | 5번 winner_brn 있는 공고만 | **5번 후 (순차)** | 쿼터 절약 |

### Mart 빌드 (Raw 직후)
| 테이블 | 주기 | 모드 |
|---|---|---|
| stg_bid_notice / stg_award / stg_opening_result | 주 1회 | full rebuild from raw |
| mart_company_master / mart_company_sr | 분기 1회 (CSV 갱신 시) + 신규 BRN incremental upsert | |
| mart_item_supply | 주 1회 | full rebuild |
| mart_features_at_bid | 월 1회 (LGBM 학습 직전) | 룰베이스 운영엔 불필요 |

### 운영 추천 (사전탐색)이 사용하는 테이블
- `mart_item_supply` + `mart_company_master` + `mart_company_sr` (Stage 1/2 룰베이스)
- `stg_award` (예상가 낙찰률 분포, 최근 낙찰 이력, 시각화)
- `stg_opening_result + stg_award` direct join (1순위 탈락 이력)
- `stg_bid_notice` (품목명 매핑, 유사 발주 사례)
- → `mart_features_at_bid` 불필요 (LGBM 학습/inference 시점에만)

### 모델
| 산출물 | 주기 | 트리거 |
|---|---|---|
| LGBM 학습 (lgbm_baseline.txt) | 월 1회 또는 데이터 +20% 시 | 수동 — `uv run python scripts/train_baseline.py` |
| 룰베이스 가중치 (`ranker.RuleRanker` weights) | 분기 검토 | 수동 |

### 자동화 단계
**Phase 1 (현재 PoC) — 로컬 cron / launchd**
- 운영팀 macOS의 launchd 또는 cron 으로 주 1회 ingest+mart 실행
- DB 는 로컬 PostgreSQL
- 단점: 운영자 PC 꺼지면 멈춤 (시범 운영 동안만 OK)

**Phase 2 (시범사업) — 클라우드 VM**
- 작은 EC2/Lightsail (월 5~10$) + crontab + 같은 인스턴스에 PostgreSQL
- 공무원은 외부 URL 로 대시보드 접속
- 운영팀이 DB/cron 관리

**Phase 3 (정식 도입) — 환경공단 내부 인프라**
- 환경공단 IT 인프라에 배포 + Airflow (Dataset 트리거 + Dynamic Task Mapping)
- 공무원 사내망에서만 접속

### "지금 갱신" 같은 사용자 트리거 — 만들지 않음
- 공무원이 ingest 트리거 = 권한·책임 떠넘기기
- 데이터 신선도가 의사결정에 critical 하지 않음 (주 1회로 충분)
- 필요 시 **운영팀 측 어드민 페이지**로 분리 (사용자 화면 X)

### 사용자 화면 표기
- 헤더 또는 KPI 영역에 1줄: "데이터 기준일: 2026-04-29 (4일 전)"
- 7일 이상 지나면 노란 경고 "데이터 갱신 지연"

### `/api/v2/meta` 엔드포인트
```json
{
  "data_cutoff": "2026-04-29T03:00:00+09:00",
  "freshness_days": 6,
  "stale_warning": false,
  "sources": {
    "stg_award": "2026-04-29",
    "mart_company_master": "2026-04-01"
  }
}
```
