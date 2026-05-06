# 한국환경공단 SR 공급망 분석 시스템

환경기초시설 관급자재 발주의 사회적 가치(SR) 공급망을 분석하고, 발주 실무자의 의사결정을 지원하는 대시보드.

---

## 🚀 팀원 온보딩 — **먼저 읽기**

### 👉 [`docs/HANDOFF.md`](./docs/HANDOFF.md)

빠른 시작 (10분) · 데이터 모델 · ER 다이어그램 · **30 피처 명세** · 추천 워크플로우 · FAQ

> AI 에이전트(Claude·Cursor 등)와 작업 시 → [`CLAUDE.md`](./CLAUDE.md) 도 같이.

---

## 빠른 시작

### 1. 환경 준비

```bash
# uv 설치 (한 번만, 미설치 시)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치 (Python 3.12 자동 + .venv 생성)
uv sync

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 G2B_SERVICE_KEY=... 입력
```

### 2. 동작 확인

```bash
# G2B OpenAPI가 정상 응답하는지 확인
uv run python scripts/check_g2b_api.py
```

### 3. 단계별 의존성 추가

```bash
uv sync --extra analysis    # Jupyter, matplotlib, plotly
uv sync --extra ml          # scikit-learn, UMAP, HDBSCAN
uv sync --extra api         # FastAPI 도입 시
uv sync --all-extras        # 전부
```

### 4. PostgreSQL 초기화 (DB 적재 단계 진입 시)

```bash
psql -U postgres -d <db_name> -f sql/init.sql
```

## 폴더 구조

| 폴더 | 용도 |
|---|---|
| `docs/` | API·데이터셋 레퍼런스 (에이전트 참조용) |
| `pipeline/` | 수집·정제 공통 Python 모듈 |
| `sql/` | PostgreSQL 스키마 |
| `scripts/` | 진단·검증 스크립트 |
| `analysis/notebooks/` | 분석용 Jupyter 노트북 |
| `data/` | 로컬 데이터 (gitignore) |

## 핵심 데이터 소스

| 소스 | 형태 | 역할 |
|---|---|---|
| 나라장터 입찰공고 (14번 API) | OpenAPI | 분석 대상 공고 풀 |
| 나라장터 낙찰자 (1번 API) | OpenAPI | BRN 추출 |
| 나라장터 개찰결과 (5번 API) | OpenAPI | 유찰·협상 식별 |
| 나라장터 복수예가 (9번 API) | OpenAPI | 예비가격 디테일 (옵션) |
| 조달업체 등록 내역 | CSV (data.go.kr/15053474) | BRN 마스터 + SR 1차 분류 |

## 분석 단위

- **세부품명번호**(10자리) × **사업자등록번호 BRN**(10자리)
- 모든 데이터셋이 이 두 키로 연결됨

## 진행 상황

MVP 1사이클 진행 중. 자세한 단계는 [`CLAUDE.md` § 10](./CLAUDE.md#10-현재-진행-상황-mvp-단계) 참조.

## 라이선스 / 데이터 출처

- 나라장터 OpenAPI: 공공데이터포털 활용신청 기반
- 조달업체 등록 내역: 조달청 (이용허락범위 제한 없음)
