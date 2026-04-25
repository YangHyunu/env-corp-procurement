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

> 새 라이브러리 추가는 **확인 사항** (4. 작업 방식 참조)

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

## 5. 폴더 구조 (단계별 성장)

빈 폴더를 미리 만들지 않습니다. **필요할 때 생성**.

### 현재 셋업 (1단계)

```
project_root/
├── CLAUDE.md                 ← 이 파일 (에이전트 첫 진입점)
├── README.md                 ← 사람용 가이드
├── .env.example              ← 환경변수 템플릿
├── .env                      ← 실제 키 (gitignore)
├── .gitignore
├── pyproject.toml            ← uv 기반 의존성 정의
├── .python-version           ← Python 3.12 고정
│
├── docs/                     ← 레퍼런스 문서 (에이전트가 자주 참조)
│   ├── _common.md            ← G2B API 공통 규칙
│   ├── api/g2b/
│   │   ├── getBidPblancListInfoThngPPSSrch.md   (14번)
│   │   ├── getScsbidListSttusThng.md            (1번)
│   │   ├── getOpengResultListInfoThng.md        (5번)
│   │   └── getOpengResultListInfoThngPreparPcDetail.md (9번)
│   └── datasets/
│       └── dataset_procurement_corp.md          (조달업체 CSV)
│
├── pipeline/                 ← 수집·정제 공통 모듈
│   ├── __init__.py
│   ├── g2b_common.py
│   └── procurement_corp.py
│
├── sql/
│   └── init.sql              ← PostgreSQL 스키마
│
├── analysis/
│   └── notebooks/            ← 탐색용 *.ipynb 자리
│
└── data/                     ← 로컬 데이터 (gitignore)
    └── raw/
```

### 향후 단계 (이때 비로소 폴더 추가)

| 단계 | 추가할 폴더 | 추가 시점 |
|---|---|---|
| 2단계 | `airflow/dags/` | 수집 스크립트 동작 검증 완료 후 |
| 3단계 | `api/` (FastAPI) | mart 테이블 빌드 완료 후 |
| 4단계 | `frontend/` (Vite+React) | API 엔드포인트 안정화 후 |
| 부수 | `analysis/reports/` | 분석 결과물이 생기면 |

> 지금 시점에 `api/`·`frontend/`·`airflow/`를 미리 만들지 마세요. **빈 폴더는 에이전트에게 "여기 뭔가 채워야 한다"는 잘못된 신호**가 됩니다.

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
- **새 라이브러리 임의 추가** — `uv add <패키지>` (또는 `pyproject.toml` 수정) + 사용자 확인. **`pip install`로 직접 설치 금지** (pyproject.toml과 어긋남)
- **PostgreSQL 스키마 임의 변경** — 마이그레이션 + 사용자 확인
- **MVP 단계에서 SR 외부 API 손대기** — v2로 미뤄둠 (현재는 조달업체 CSV의 1차 분류만 사용)

---

## 10. 현재 진행 상황 (MVP 단계)

### 완료
- [x] G2B API 4개 명세 분석 (`docs/api/g2b/`)
- [x] 조달업체 CSV 분석 (`docs/datasets/`)
- [x] 공통 규칙 정의 (`docs/_common.md`)
- [x] `pipeline/g2b_common.py` 구현 (BRN 정규화, 페이징, 재시도)
- [x] `pipeline/procurement_corp.py` 구현 (CSV 로딩, 정규화)
- [x] 환경공단 dminsttCd 10개 실측 확정

### 진행 예정 (MVP 한 사이클)
- [ ] PostgreSQL 스키마 (`sql/init.sql`)
- [ ] 14번 수집 → 환경공단 공고 적재
- [ ] 1번 수집 → BRN 추출
- [ ] 조달업체 CSV 적재 → `mart_company_master`
- [ ] 낙찰자 BRN ↔ CSV left join 검증
- [ ] FastAPI 기본 엔드포인트 (`/api/items`, `/api/recommend`)
- [ ] React 대시보드 프로토타입

### v2 (MVP 이후)
- 외부 SR API 연동 (인증서 유효성 보강)
- 부정당제재 정보
- 클러스터링 모델 튜닝
- 발주 의사결정 엔진 본격화
