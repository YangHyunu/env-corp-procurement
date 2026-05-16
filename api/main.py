"""
FastAPI 골격 — pipeline.scoring 을 HTTP로 노출.

실행:
  uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.schemas import (  # noqa: E402
    CompanyAward,
    CompanyDetail,
    ItemSummary,
    KpiResponse,
    MetaResponse,
    RecommendRequest,
    RecommendResponse,
    RecommendV2Request,
    RecommendV2Response,
    RecommendationItem,
)
from pipeline.item_keywords import KEYWORDS  # noqa: E402
from pipeline.recommend_v2 import (  # noqa: E402
    RecommendV2Request as RecommendV2DTO,
    recommend as recommend_v2,
)
from pipeline.scoring import (  # noqa: E402
    DEFAULT_WEIGHTS,
    SrFilter,
    score,
)

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

app = FastAPI(
    title="ECO Procurement Recommendation API",
    description="환경공단 관급자재 SR 공급망 분석 — 추천 스코어링 백엔드",
    version="0.1.0",
)

# CORS (Vite dev + ngrok 등)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # MVP, 운영시 origin 제한
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _query(sql: str, params=None) -> list[dict]:
    with psycopg2.connect(DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


@app.get("/healthz")
def healthz() -> dict:
    try:
        rows = _query("SELECT 1 AS ok")
        return {"status": "ok", "db": rows[0]["ok"] == 1}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── /api/items ──────────────────────────────────────────────
@app.get("/api/items", response_model=list[ItemSummary])
def list_items(
    q: str | None = Query(None, description="품명/품명번호 부분 일치"),
    limit: int = Query(20, ge=1, le=200),
) -> list[ItemSummary]:
    """환경공단 1년치 발주 품목 검색."""
    if q:
        sql = """
        SELECT dtil_prdct_clsfc_no AS item_code,
               MAX(dtil_prdct_clsfc_no_nm) AS item_name,
               COUNT(*) AS bid_count
        FROM stg_bid_notice
        WHERE is_env_corp
          AND (dtil_prdct_clsfc_no LIKE %s
               OR dtil_prdct_clsfc_no_nm ILIKE %s)
        GROUP BY 1 ORDER BY bid_count DESC LIMIT %s
        """
        like = f"%{q}%"
        rows = _query(sql, (like, like, limit))
    else:
        sql = """
        SELECT dtil_prdct_clsfc_no AS item_code,
               MAX(dtil_prdct_clsfc_no_nm) AS item_name,
               COUNT(*) AS bid_count
        FROM stg_bid_notice
        WHERE is_env_corp AND dtil_prdct_clsfc_no IS NOT NULL
        GROUP BY 1 ORDER BY bid_count DESC LIMIT %s
        """
        rows = _query(sql, (limit,))
    return [ItemSummary(**r) for r in rows]


# ── /api/recommend ──────────────────────────────────────────
@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    """top-K 추천 — pipeline.scoring.score wrap."""
    weights = (
        req.weights.model_dump()
        if req.weights
        else DEFAULT_WEIGHTS
    )
    sr_filter = (
        SrFilter(**req.sr_filter.model_dump())
        if req.sr_filter
        else None
    )
    try:
        result = score(
            req.item_code,
            weights=weights,
            sr_filter=sr_filter,
            top_k=req.top_k,
            dsn=DSN,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RecommendResponse(
        item_code=result.item_code,
        matched_count=result.matched_count,
        sr_coverage_pct=result.sr_coverage_pct,
        recommendations=[
            RecommendationItem(
                rank=r.rank,
                brn=r.brn,
                corp_name=r.corp_name,
                composite_score=r.composite_score,
                axes=r.axes,
                weighted_segments=r.weighted_segments,
                sr_badges=r.sr_badges,
                award_summary=r.award_summary,
                reason=r.reason,
                is_sr_demoted=r.is_sr_demoted,
            )
            for r in result.recommendations
        ],
        meta=result.meta,
    )


# ── /api/company/{brn} ──────────────────────────────────────
@app.get("/api/company/{brn}", response_model=CompanyDetail)
def company_detail(brn: str) -> CompanyDetail:
    """클릭 펼침 — 업체 정보 + 환경공단 낙찰 이력."""
    if not brn.isdigit() and not (brn.startswith("F") and len(brn) == 10):
        raise HTTPException(status_code=400, detail="invalid BRN format")

    head = _query("""
        SELECT m.brn, m.corp_name, m.corp_size, m.region_code,
               m.addr_sigungu, m.is_manufacturer, m.g2b_registered_at,
               s.sr_count, s.female_ceo_flag, s.disabled_corp_flag, s.social_corp_flag
        FROM mart_company_master m
        JOIN mart_company_sr     s USING (brn)
        WHERE m.brn = %s
    """, (brn,))
    if not head:
        raise HTTPException(status_code=404, detail="BRN not found")
    h = head[0]

    sr_badges: list[str] = []
    if h["female_ceo_flag"]:
        sr_badges.append("여성기업(자동판별)")
    if h["disabled_corp_flag"]:
        sr_badges.append("장애인기업")
    if h["social_corp_flag"]:
        sr_badges.append("사회적기업")

    awards = _query("""
        SELECT a.bid_ntce_no,
               a.bid_ntce_nm,
               a.fnl_sucsf_date::text,
               a.sucsfbid_amt,
               a.sucsfbid_rate,
               a.dminstt_nm,
               b.dtil_prdct_clsfc_no    AS item_code,
               b.dtil_prdct_clsfc_no_nm AS item_name
        FROM stg_award a
        LEFT JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
        WHERE a.bidwinnr_brn = %s
        ORDER BY a.fnl_sucsf_date DESC NULLS LAST
        LIMIT 50
    """, (brn,))

    award_total = _query("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(sucsfbid_amt),0)::bigint AS total
        FROM stg_award WHERE bidwinnr_brn = %s
    """, (brn,))[0]

    return CompanyDetail(
        brn=h["brn"],
        corp_name=h["corp_name"],
        corp_size=h["corp_size"],
        region_code=h["region_code"],
        addr_sigungu=h["addr_sigungu"],
        is_manufacturer=h["is_manufacturer"],
        sr_count=h["sr_count"],
        sr_badges=sr_badges,
        g2b_registered_at=h["g2b_registered_at"].isoformat() if h["g2b_registered_at"] else None,
        awards=[CompanyAward(**a) for a in awards],
        award_total_count=int(award_total["cnt"]),
        award_total_amt=int(award_total["total"]),
    )


# ── /api/kpi/{item_code} ────────────────────────────────────
@app.get("/api/kpi/{item_code}", response_model=KpiResponse)
def kpi(item_code: str) -> KpiResponse:
    """KPI 카드 4개."""
    name_row = _query("""
        SELECT MAX(dtil_prdct_clsfc_no_nm) AS item_name
        FROM stg_bid_notice WHERE dtil_prdct_clsfc_no = %s
    """, (item_code,))
    item_name = name_row[0]["item_name"] if name_row else None

    pool = _query("""
        SELECT COUNT(*) AS pool,
               SUM(CASE WHEN s.sr_count > 0 THEN 1 ELSE 0 END) AS sr_brn
        FROM mart_item_supply mis
        JOIN mart_company_sr s USING (brn)
        WHERE mis.dtil_prdct_clsfc_no = %s
    """, (item_code,))[0]
    if pool["pool"] == 0:
        raise HTTPException(status_code=404, detail="ITEM_NOT_FOUND")

    sr_pct = 100.0 * (pool["sr_brn"] or 0) / pool["pool"]

    # 추천 임계 (composite >= 0.5) 비율 — score를 한 번 돌려야 정확한데
    # KPI는 가벼움 우선 → top-K 안 보고 default 가중치로 전체 풀 계산
    try:
        rec = score(item_code, top_k=int(pool["pool"]), dsn=DSN)
        passing = sum(1 for r in rec.recommendations if r.composite_score >= 0.5)
        rec_pct = 100.0 * passing / max(rec.matched_count, 1)
    except Exception:
        rec_pct = 0.0

    return KpiResponse(
        item_code=item_code,
        item_name=item_name,
        matched_count=int(pool["pool"]),
        sr_coverage_pct=sr_pct,
        cluster_count=None,        # MVP 스텁 — D2 결정 시 채움 (docs/decisions/2026-05-16_team_integration_meeting.md)
        recommend_threshold_pct=rec_pct,
    )


# ─── v2: 사전탐색 모드 ──────────────────────────────────────────────
@app.get("/api/v2/keywords", response_model=list[str])
def list_keywords() -> list[str]:
    """8개 자연어 품목 키워드 목록 (프론트 칩 그리기용)."""
    return KEYWORDS


@app.post("/api/v2/recommend", response_model=RecommendV2Response)
def recommend_v2_endpoint(req: RecommendV2Request) -> RecommendV2Response:
    """사전탐색 추천 — 키워드 + 정책 필터 + 예산 → top-K BRN."""
    try:
        return recommend_v2(
            RecommendV2DTO(
                item_keyword=req.item_keyword,
                budget_million_won=req.budget_million_won,
                sr_filter=req.sr_filter.model_dump(),
                top_k=req.top_k,
            ),
            dsn=DSN,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    """데이터 기준일 + 신선도 (헤더 표기용)."""
    rows = _query("""
        SELECT 'stg_award' AS src, MAX(fetched_at) AS ts FROM stg_award
        UNION ALL
        SELECT 'stg_bid_notice', MAX(fetched_at) FROM stg_bid_notice
        UNION ALL
        SELECT 'stg_opening_result', MAX(fetched_at) FROM stg_opening_result
        UNION ALL
        SELECT 'mart_company_master', MAX(last_synced_at) FROM mart_company_master
    """)
    sources = {r["src"]: (r["ts"].isoformat() if r["ts"] else "") for r in rows}
    valid_ts = [r["ts"] for r in rows if r["ts"] is not None]
    if valid_ts:
        cutoff = min(valid_ts)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        delta_days = (now - cutoff).days
    else:
        from datetime import datetime, timezone
        cutoff = datetime.now(timezone.utc)
        delta_days = 0
    return MetaResponse(
        data_cutoff=cutoff.isoformat(),
        freshness_days=delta_days,
        stale_warning=delta_days > 7,
        sources=sources,
    )
