"""
사전탐색 모드 v2 — Two-Stage 추천 오케스트레이션.

  Stage 1 (retrieve): 키워드+정책 → 후보 BRN 풀
  Stage 2 (rank):     RuleRanker (또는 향후 LGBMRanker) 점수
  Enrich:             카드 디테일 (예상가/리스크/전례/시각화)

진입점: recommend(req)

DB 연결: recommend() 가 한 요청당 단 한 번만 connect 한다 (`_connect`).
모든 헬퍼는 `conn`을 인자로 받는다 — DSN 스트링은 entry-point 만 처리.
"""
from __future__ import annotations

import csv
import functools
import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

from api.schemas import (
    AwardItemV2,
    ChartsData,
    ComplianceInfo,
    ExpectedPrice,
    KpiV2,
    MarketDepth,
    PrecedentItem,
    RecommendationV2Item,
    RecommendV2Response,
    RiskInfo,
    SummaryStatsV2,
    SupplyStability,
)
from pipeline.item_keywords import KeywordFilter, resolve as resolve_keyword
from pipeline.policy import SR_LEGAL_FLOOR_PCT
from pipeline.ranker import Ranker, RuleRanker

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logger = logging.getLogger(__name__)


# ── K-NN cold-start artifact (장애인기업 narrative 보강용) ──
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
KNN_CANDIDATES_PATH = ARTIFACTS_DIR / "disabled_knn_candidates.csv"


@functools.lru_cache(maxsize=1)
def _load_knn_lookup() -> dict[str, dict[str, Any]]:
    """cold_brn → {ref_brn, ref_corp_name, similarity} dict.

    disabled_knn_candidates.csv 의 cold-start BRN별 top1 유사 회사.
    파일 부재 시 빈 dict.
    """
    out: dict[str, dict[str, Any]] = {}
    if not KNN_CANDIDATES_PATH.exists():
        return out
    try:
        with open(KNN_CANDIDATES_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brn = (row.get("brn") or "").strip()
                ref_brn = (row.get("nearest_ref_brn") or "").strip()
                ref_name = (row.get("nearest_ref_name") or "").strip() or None
                # US-003: 빈 값 / 0 / 음수 / parse 실패 row 는 skip
                try:
                    sim = float(row.get("similarity") or 0.0)
                except ValueError:
                    continue
                if sim <= 0:
                    continue
                if brn and ref_brn:
                    out[brn] = {
                        "ref_brn": ref_brn,
                        "ref_corp_name": ref_name,
                        "similarity": sim,
                    }
    except OSError as exc:
        logger.warning("KNN candidates load failed: %s", exc)
    return out


def _is_cold_or_dormant(c: dict) -> bool:
    """BRN이 cold-start인지 — K-NN narrative 보강 트리거 조건.

    환경공단 낙찰 이력이 없는 BRN(env_count == 0) 만 보강 대상.
    """
    return int(c.get("award_count") or 0) == 0


# ── Domain thresholds (CLAUDE.md §11 리스크 등급 4단계 표와 동기화) ──────
RISK_LOST_HARD: int = 3            # 누적 1순위→탈락 횟수 hard cap
RISK_LOST_RATIO: float = 0.30      # 탈락/top1 비율 hard cap
RISK_RECENT_LOST: int = 2          # 최근 1년 탈락 hard cap
RISK_TOP1_SAFE: int = 3            # 안전 등급 진입 최소 top1 카운트
TIER_A_CUTOFF: float = 0.6         # rule_score ≥ A 강추
TIER_B_CUTOFF: float = 0.3         # rule_score ≥ B 추천
DORMANT_MONTHS: int = 24           # 활동중단 판정 임계 (개월)
PRECEDENT_BUDGET_LO: float = 0.5   # 유사발주 예산 하단 배수
PRECEDENT_BUDGET_HI: float = 1.5   # 유사발주 예산 상단 배수
MONTH_DAYS: float = 30.4           # 평균 1개월 일수 (Julian 평균)


@dataclass
class RecommendV2Request:
    item_keyword: str
    budget_million_won: int
    sr_filter: dict[str, bool]      # {social_corp, female_ceo, disabled_corp}
    top_k: int = 5


# ── DB connection (single source — only place that opens a DB connection) ──
@contextmanager
def _connect(dsn: str) -> Iterator[Any]:
    """모든 헬퍼가 공유하는 단일 connection lifecycle."""
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def _dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Stage 1: Retrieve ───────────────────────────────────────────────
RETRIEVE_SQL = """
WITH item_name_map AS (
  SELECT DISTINCT dtil_prdct_clsfc_no, dtil_prdct_clsfc_no_nm
  FROM stg_bid_notice WHERE dtil_prdct_clsfc_no_nm IS NOT NULL
),
warm_brns AS (
  SELECT DISTINCT bidwinnr_brn AS brn FROM stg_award a
  JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
  WHERE b.agency_tier IN ('env_corp', 'env_domain') AND a.bidwinnr_brn IS NOT NULL
),
candidate_brns AS (
  -- (a) 등록 BRN ∩ warm 풀 (mart_item_supply 기반)
  SELECT DISTINCT mis.brn
  FROM mart_item_supply mis
  JOIN item_name_map inm USING (dtil_prdct_clsfc_no)
  JOIN warm_brns wb ON wb.brn = mis.brn
  WHERE LEFT(mis.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
    AND inm.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
  UNION
  -- (b) 매칭 품목 실제 낙찰 이력자 (등록 미반영 BRN 보완 — env_domain 확장 효과)
  SELECT DISTINCT a.bidwinnr_brn AS brn
  FROM stg_award a
  JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
  WHERE b.agency_tier IN ('env_corp', 'env_domain')
    AND a.bidwinnr_brn IS NOT NULL
    AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
    AND b.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
),
brn_env_stats AS (
  SELECT a.bidwinnr_brn AS brn,
         COUNT(*) AS award_count,
         COALESCE(SUM(a.sucsfbid_amt), 0) AS award_total_amt,
         AVG(a.sucsfbid_rate) AS avg_bid_rate,
         MAX(a.fnl_sucsf_date) AS last_award_at
  FROM stg_award a
  JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
  WHERE b.agency_tier IN ('env_corp', 'env_domain') AND a.bidwinnr_brn IS NOT NULL
  GROUP BY 1
)
SELECT cb.brn,
       COALESCE(s.award_count, 0)     AS award_count,
       COALESCE(s.award_total_amt, 0) AS award_total_amt,
       s.avg_bid_rate, s.last_award_at,
       mcs.sr_count, mcs.female_ceo_flag, mcs.disabled_corp_flag, mcs.social_corp_flag,
       mcm.corp_name, mcm.corp_size, mcm.is_manufacturer,
       mcm.g2b_registered_at, mcm.region_code, mcm.addr_sigungu
FROM candidate_brns cb
JOIN mart_company_sr mcs USING (brn)
JOIN mart_company_master mcm USING (brn)
LEFT JOIN brn_env_stats s USING (brn)
WHERE 1=1 {sr_clause}
"""


def _build_sr_clause(sr_filter: dict[str, bool]) -> str:
    parts: list[str] = []
    if sr_filter.get("female_ceo"):
        parts.append("AND mcs.female_ceo_flag")
    if sr_filter.get("disabled_corp"):
        parts.append("AND mcs.disabled_corp_flag")
    if sr_filter.get("social_corp"):
        parts.append("AND mcs.social_corp_flag")
    return " ".join(parts)


def retrieve(
    conn, keyword: str, sr_filter: dict[str, bool],
) -> tuple[list[dict], KeywordFilter]:
    kf = resolve_keyword(keyword)
    sql = RETRIEVE_SQL.format(sr_clause=_build_sr_clause(sr_filter))
    with _dict_cursor(conn) as cur:
        cur.execute(sql, {"prefix4": kf.prefix4, "name_regex": kf.name_regex})
        rows = [dict(r) for r in cur.fetchall()]
    return rows, kf


# ── Stage 2: Rank ───────────────────────────────────────────────────
def rank(
    candidates: list[dict], context: dict, ranker: Optional[Ranker] = None,
) -> list[dict]:
    return (ranker or RuleRanker()).score(candidates, context)


# ── Enrich helpers (all take conn) ──────────────────────────────────
def _market_baseline(conn, prefix4: list[str], name_regex: str) -> dict:
    sql = """
    SELECT
      COUNT(*) AS n,
      AVG(a.sucsfbid_rate)  AS mean,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q25,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q75,
      STDDEV(a.sucsfbid_rate) AS std
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
      AND b.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
      AND a.sucsfbid_rate IS NOT NULL
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, {"prefix4": prefix4, "name_regex": name_regex})
        r = cur.fetchone() or {}
    return {
        "n": int(r.get("n") or 0),
        "mean": float(r["mean"]) if r.get("mean") is not None else None,
        "q25":  float(r["q25"])  if r.get("q25")  is not None else None,
        "q75":  float(r["q75"])  if r.get("q75")  is not None else None,
        "std":  float(r["std"])  if r.get("std")  is not None else None,
    }


def _brn_rate_distribution(conn, brns: list[str]) -> dict[str, dict]:
    if not brns:
        return {}
    sql = """
    SELECT a.bidwinnr_brn AS brn,
           COUNT(*) AS n,
           AVG(a.sucsfbid_rate) AS mean,
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q25,
           PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q75,
           STDDEV(a.sucsfbid_rate) AS std,
           ARRAY_AGG(a.sucsfbid_rate ORDER BY a.fnl_sucsf_date) AS rates,
           ARRAY_AGG(a.sucsfbid_amt  ORDER BY a.fnl_sucsf_date) AS amts
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND a.bidwinnr_brn = ANY(%s)
      AND a.sucsfbid_rate IS NOT NULL
    GROUP BY 1
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (brns,))
        return {r["brn"]: dict(r) for r in cur.fetchall()}


# ── 유사 규모 한정 분포 (외삽 방지) ─────────────────────────────────
PRICE_SCALE_BAND_LO: float = 0.5    # 입력 예산 × 0.5 ~
PRICE_SCALE_BAND_HI: float = 1.5    # 입력 예산 × 1.5


def _brn_rate_distribution_at_scale(
    conn, brns: list[str], budget_won: int,
) -> dict[str, dict]:
    """BRN의 유사 규모 (예산 ±50%) 거래 분포만 추출.

    n_samples_at_scale ≥ 3 이면 BRN 데이터로 신뢰성 있는 점/구간 산출.
    n=0 이면 외삽 위험 시그널 — 시장 fallback 또는 is_extrapolated 표시.
    """
    if not brns:
        return {}
    lo = int(budget_won * PRICE_SCALE_BAND_LO)
    hi = int(budget_won * PRICE_SCALE_BAND_HI)
    sql = """
    SELECT a.bidwinnr_brn AS brn,
           COUNT(*) AS n,
           AVG(a.sucsfbid_rate) AS mean,
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q25,
           PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q75,
           STDDEV(a.sucsfbid_rate) AS std
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND a.bidwinnr_brn = ANY(%s)
      AND a.sucsfbid_rate IS NOT NULL
      AND a.sucsfbid_amt BETWEEN %s AND %s
    GROUP BY 1
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (brns, lo, hi))
        return {r["brn"]: dict(r) for r in cur.fetchall()}


def _market_baseline_at_scale(
    conn, prefix4: list[str], name_regex: str, budget_won: int,
) -> dict:
    """입력 예산 ±50% 범위 시장 baseline (BRN 데이터 부족 시 fallback)."""
    lo = int(budget_won * PRICE_SCALE_BAND_LO)
    hi = int(budget_won * PRICE_SCALE_BAND_HI)
    sql = """
    SELECT
      COUNT(*) AS n,
      AVG(a.sucsfbid_rate)  AS mean,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q25,
      PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q50,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q75,
      STDDEV(a.sucsfbid_rate) AS std
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
      AND b.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
      AND a.sucsfbid_rate IS NOT NULL
      AND a.sucsfbid_amt BETWEEN %(lo)s AND %(hi)s
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, {
            "prefix4": prefix4, "name_regex": name_regex,
            "lo": lo, "hi": hi,
        })
        r = cur.fetchone() or {}
    return {
        "n": int(r.get("n") or 0),
        "mean": float(r["mean"]) if r.get("mean") is not None else None,
        "q25":  float(r["q25"])  if r.get("q25")  is not None else None,
        "q50":  float(r["q50"])  if r.get("q50")  is not None else None,
        "q75":  float(r["q75"])  if r.get("q75")  is not None else None,
        "std":  float(r["std"])  if r.get("std")  is not None else None,
    }


def _brn_risk_signals(conn, brns: list[str]) -> dict[str, dict]:
    if not brns:
        return {}
    sql = """
    WITH top1 AS (
      SELECT o.winner_brn AS brn, o.bid_ntce_no, o.bid_ntce_ord, o.openg_dt,
             a.bidwinnr_brn AS final_brn
      FROM stg_opening_result o
      LEFT JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
      JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
      WHERE b.agency_tier IN ('env_corp', 'env_domain') AND o.winner_brn IS NOT NULL AND o.rbid_no='000'
    )
    SELECT brn,
           COUNT(*) AS top1_count,
           COUNT(*) FILTER (WHERE final_brn IS NULL OR final_brn != brn) AS lost_count,
           COUNT(*) FILTER (WHERE (final_brn IS NULL OR final_brn != brn)
                              AND openg_dt >= NOW() - INTERVAL '1 year') AS recent_lost
    FROM top1
    WHERE brn = ANY(%s)
    GROUP BY 1
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (brns,))
        return {r["brn"]: dict(r) for r in cur.fetchall()}


def _brn_recent_awards(conn, brns: list[str], n: int = 5) -> dict[str, list[dict]]:
    if not brns:
        return {}
    sql = """
    SELECT b.brn, x.*
    FROM unnest(%s::text[]) AS b(brn)
    JOIN LATERAL (
      SELECT bid_ntce_no, bid_ntce_nm,
             fnl_sucsf_date::text AS fnl_sucsf_date,
             sucsfbid_amt, sucsfbid_rate
      FROM stg_award a
      WHERE a.bidwinnr_brn = b.brn
      ORDER BY a.fnl_sucsf_date DESC NULLS LAST
      LIMIT %s
    ) x ON TRUE
    """
    out: dict[str, list[dict]] = {}
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (brns, n))
        for row in cur.fetchall():
            out.setdefault(row["brn"], []).append(
                {k: v for k, v in row.items() if k != "brn"}
            )
    return out


def _precedents(
    conn, prefix4: list[str], name_regex: str, budget_won: int, n: int = 5,
) -> list[dict]:
    sql = """
    SELECT b.bid_ntce_no, b.bid_ntce_nm,
           a.fnl_sucsf_date::text AS fnl_sucsf_date,
           a.sucsfbid_amt,
           a.bidwinnr_brn,
           a.bidwinnr_nm AS winner_corp_name
    FROM stg_bid_notice b
    JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%s)
      AND b.dtil_prdct_clsfc_no_nm ~ %s
      AND a.sucsfbid_amt BETWEEN %s AND %s
    ORDER BY a.fnl_sucsf_date DESC NULLS LAST
    LIMIT %s
    """
    with _dict_cursor(conn) as cur:
        cur.execute(
            sql,
            (prefix4, name_regex,
             int(budget_won * PRECEDENT_BUDGET_LO),
             int(budget_won * PRECEDENT_BUDGET_HI), n),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Risk grade / Tier / Helpers (pure functions — no DB) ────────────
def _risk_grade(top1: int, lost: int, recent_lost: int) -> str:
    if top1 == 0:
        return "미확인"
    ratio = lost / top1
    if lost >= RISK_LOST_HARD or ratio >= RISK_LOST_RATIO or recent_lost >= RISK_RECENT_LOST:
        return "주의"
    if top1 >= RISK_TOP1_SAFE and lost == 0:
        return "안전"
    return "양호"


def _tier(rule_score: float, risk_grade: str) -> str:
    if risk_grade == "주의":
        return "C"
    if rule_score >= TIER_A_CUTOFF:
        return "A"
    if rule_score >= TIER_B_CUTOFF:
        return "B"
    return "C"


def _dormant_months(last_award_at) -> Optional[int]:
    if not last_award_at:
        return None
    if hasattr(last_award_at, "tzinfo") and last_award_at.tzinfo:
        diff = datetime.now(timezone.utc) - last_award_at
    else:
        diff = datetime.now() - datetime.combine(last_award_at, datetime.min.time())
    return int(diff.days / MONTH_DAYS)


def _badges(c: dict) -> list[str]:
    out: list[str] = []
    if c.get("corp_size"):
        out.append(c["corp_size"])
    sigungu = c.get("addr_sigungu") or ""
    if sigungu:
        first = sigungu.split()[0] if sigungu.split() else ""
        if first:
            short = (
                first.replace("광역시", "")
                     .replace("특별시", "")
                     .replace("특별자치시", "")
                     .replace("특별자치도", "")
            )
            out.append(short[:3] or first[:3])
    if c.get("female_ceo_flag"):
        out.append("여성기업")
    if c.get("disabled_corp_flag"):
        out.append("장애인기업")
    if c.get("social_corp_flag"):
        out.append("사회적기업")
    return out


def _reason(c: dict, market_mean: Optional[float]) -> str:
    parts: list[str] = []
    if c.get("award_count", 0) > 0:
        parts.append(f"환경공단 누적 {c['award_count']}건")
        ar = c.get("avg_bid_rate")
        if ar is not None:
            ar = float(ar)
            if market_mean and ar < market_mean - 1.0:
                parts.append(f"평균 낙찰률 {ar:.1f}% (시장 대비 저렴)")
            elif market_mean and ar > market_mean + 1.0:
                parts.append(f"평균 낙찰률 {ar:.1f}% (시장 대비 비쌈)")
            else:
                parts.append(f"평균 낙찰률 {ar:.1f}%")
    else:
        parts.append("환경공단 활동 이력 부족")
    sr_labels: list[str] = []
    if c.get("female_ceo_flag"):
        sr_labels.append("여성")
    if c.get("disabled_corp_flag"):
        sr_labels.append("장애인")
    if c.get("social_corp_flag"):
        sr_labels.append("사회적")
    if sr_labels:
        parts.append("+".join(sr_labels) + "기업 가점")
    return " · ".join(parts)


# ── Pure builders (no DB — unit-testable) ──────────────────────────
def _to_million(amt: Optional[int]) -> Optional[int]:
    return round(amt / 1_000_000) if amt is not None else None


def _make_expected_price(
    budget_won: int,
    dist: dict,             # BRN 전체 거래 분포
    dist_at_scale: dict,    # BRN 유사 규모 (예산 ±50%) 분포
    market: dict,           # 시장 (전체 prefix4)
    market_at_scale: dict,  # 시장 (유사 규모)
) -> dict:
    """예상가 추정 — 유사 규모 한정 + 외삽 경고.

    Fallback 우선순위:
      1. BRN 유사 규모 n≥3 → 점/구간/변동폭 모두 산출 (가장 정확)
      2. BRN 유사 규모 n=1~2 → 점추정만, 구간 X
      3. 시장 유사 규모 n≥3 → 시장 평균으로 점추정 (BRN 외삽 방지)
      4. BRN 전체 평균 (n≥3) → 외삽 경고 표시
      5. 시장 전체 평균 → 마지막 fallback
      6. 데이터 0 → 예산 그대로

    is_extrapolated=True: BRN 유사 규모 거래 부재 시 — 운영자에게 신뢰도 낮음 알림.

    [Phase 향후 swap point — 회귀 모델 도입 시 이 함수만 교체]
    (D3.B / regressor 도입 시 본 함수만 교체. 호출부는 enrich() 의 한 곳.
     반환 dict 키 — point/q25/q75/sigma_pp/market_diff_pp/n_samples/is_extrapolated —
     은 ExpectedPrice 스키마 계약이므로 유지.)
    """
    n_scale = int(dist_at_scale.get("n") or 0)
    n_full = int(dist.get("n") or 0)
    n_market_scale = int(market_at_scale.get("n") or 0)

    extrapolated = False
    sigma = None
    q25_rate = q75_rate = None

    if n_scale >= 3:
        # 1. BRN 유사 규모 — 가장 정확
        rate = dist_at_scale["mean"]
        q25_rate = dist_at_scale.get("q25")
        q75_rate = dist_at_scale.get("q75")
        sigma = dist_at_scale.get("std")
        ref_market_mean = market_at_scale.get("mean") or market.get("mean")
    elif n_scale >= 1:
        # 2. BRN 유사 규모 1~2건 — 점추정만
        rate = dist_at_scale["mean"]
        ref_market_mean = market_at_scale.get("mean") or market.get("mean")
    elif n_market_scale >= 3:
        # 3. 시장 유사 규모 fallback — BRN 외삽 방지
        rate = market_at_scale["mean"]
        ref_market_mean = market_at_scale["mean"]
        extrapolated = True
    elif n_full >= 3:
        # 4. BRN 전체 평균 — 외삽 경고
        rate = dist["mean"]
        ref_market_mean = market.get("mean")
        extrapolated = True
    elif market.get("mean") is not None:
        # 5. 시장 전체 평균
        rate = market["mean"]
        ref_market_mean = market["mean"]
        extrapolated = True
    else:
        # 6. 데이터 부재
        rate = None
        ref_market_mean = None
        extrapolated = True

    point = int(budget_won * float(rate) / 100.0) if rate is not None else budget_won
    q25 = int(budget_won * float(q25_rate) / 100.0) if q25_rate is not None else None
    q75 = int(budget_won * float(q75_rate) / 100.0) if q75_rate is not None else None
    market_diff = (
        float(rate) - float(ref_market_mean)
        if rate is not None and ref_market_mean is not None and not extrapolated
        else None
    )

    n_used = n_scale if n_scale > 0 else (n_market_scale if n_market_scale >= 3 else n_full)

    # 시장 분위수 (예산 ±50% 범위, n_market_scale ≥ 3 일 때만 산출)
    mq25_million: float | None = None
    mq50_million: float | None = None
    mq75_million: float | None = None
    if n_market_scale >= 3:
        budget_million = budget_won / 1_000_000
        mq25_rate = market_at_scale.get("q25")
        mq50_rate = market_at_scale.get("q50")
        mq75_rate = market_at_scale.get("q75")
        if mq25_rate is not None:
            mq25_million = round(budget_million * float(mq25_rate) / 100.0, 1)
        if mq50_rate is not None:
            mq50_million = round(budget_million * float(mq50_rate) / 100.0, 1)
        if mq75_rate is not None:
            mq75_million = round(budget_million * float(mq75_rate) / 100.0, 1)

    return {
        "point": point,
        "point_million": _to_million(point),
        "q25": q25, "q75": q75,
        "q25_million": _to_million(q25), "q75_million": _to_million(q75),
        "sigma_pp": round(sigma, 2) if sigma is not None else None,
        "market_diff_pp": round(market_diff, 2) if market_diff is not None else None,
        "n_samples": n_used,
        "n_samples_overall": n_full,
        "is_extrapolated": extrapolated,
        "market_q25_million": mq25_million,
        "market_q50_million": mq50_million,
        "market_q75_million": mq75_million,
    }


def _make_risk_info(last_award_at, rs: dict) -> dict:
    """리스크 등급 + 카운터 + 활동중단."""
    top1 = int(rs.get("top1_count") or 0)
    lost = int(rs.get("lost_count") or 0)
    recent = int(rs.get("recent_lost") or 0)
    ratio = (lost / top1) if top1 else 0.0
    dormant = _dormant_months(last_award_at)
    return {
        "grade":          _risk_grade(top1, lost, recent),
        "top1_count":     top1,
        "lost_count":     lost,
        "lost_ratio":     round(ratio, 3),
        "recent_lost":    recent,
        "dormant_months": dormant,
        "is_dormant":     bool(dormant is not None and dormant >= DORMANT_MONTHS),
    }


def _make_supply_stability(c: dict, brn: str) -> dict:
    """공급 안정성 — g2b_age 계산 실패는 logger.warning 후 None."""
    g2b_age = None
    reg = c.get("g2b_registered_at")
    if reg:
        try:
            g2b_age = round((datetime.now().date() - reg).days / 365.25, 1)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "g2b_age compute failed for brn=%s reg=%r: %s", brn, reg, exc
            )
    return {
        "g2b_age_years":   g2b_age,
        "award_total_amt": int(c.get("award_total_amt") or 0),
        "is_manufacturer": bool(c.get("is_manufacturer")),
        "last_award_at":   c["last_award_at"].isoformat() if c.get("last_award_at") else None,
    }


def _make_charts(dist: dict) -> dict:
    rates = list(dist.get("rates") or [])
    amts = list(dist.get("amts") or [])
    return {
        "bid_rate_distribution": [float(r) for r in rates],
        "bid_amt_distribution":  [int(a) for a in amts],
    }


@dataclass
class CardContext:
    """단일 카드 조립용 컨텍스트.

    enrich() 가 BRN별로 조립해 _build_recommendation_item 에 전달.
    DB 의존성 X — pure dataclass.
    """
    budget_won: int
    market: dict
    market_at_scale: dict
    dist: dict
    dist_at_scale: dict
    risk_signals: dict
    awards: list[dict]
    precedents: list[dict]
    knn_ref: dict[str, Any] | None = None


def _build_recommendation_item(
    rank_pos: int, c: dict, ctx: CardContext,
) -> RecommendationV2Item:
    """단일 카드 조립 — Pydantic 모델 직접 반환 (compile-time 계약)."""
    brn = c["brn"]
    risk_info = _make_risk_info(c.get("last_award_at"), ctx.risk_signals)
    reason_text = _reason(c, ctx.market.get("mean"))
    # K-NN 보조 narrative (cold-start BRN 만)
    knn_brn = knn_corp = None
    knn_sim = None
    if ctx.knn_ref:
        knn_brn = ctx.knn_ref.get("ref_brn")
        knn_corp = ctx.knn_ref.get("ref_corp_name")
        knn_sim = ctx.knn_ref.get("similarity")
        if knn_corp and knn_sim is not None:
            reason_text = (
                f"{reason_text} · {knn_corp}와 {knn_sim*100:.0f}% 유사"
            )
    return RecommendationV2Item(
        rank=rank_pos,
        brn=brn,
        corp_name=c.get("corp_name"),
        tier=_tier(c["rule_score"], risk_info["grade"]),
        badges=_badges(c),
        summary_stats=SummaryStatsV2(
            award_count=int(c.get("award_count") or 0),
            avg_bid_rate=float(c["avg_bid_rate"]) if c.get("avg_bid_rate") is not None else None,
            last_award_at=c["last_award_at"].isoformat() if c.get("last_award_at") else None,
            lost_count=risk_info["lost_count"],
        ),
        expected_price=ExpectedPrice(**_make_expected_price(
            ctx.budget_won, ctx.dist, ctx.dist_at_scale, ctx.market, ctx.market_at_scale,
        )),
        risk=RiskInfo(**risk_info),
        supply_stability=SupplyStability(**_make_supply_stability(c, brn)),
        recent_awards=[AwardItemV2(**a) for a in ctx.awards],
        precedents=[PrecedentItem(**p) for p in ctx.precedents],
        charts=ChartsData(**_make_charts(ctx.dist)),
        rule_score=float(c["rule_score"]),
        axes=c["axes"],
        ml_score=None,
        score_used=str(c.get("score_used") or "rule"),
        knn_similar_brn=knn_brn,
        knn_similar_corp_name=knn_corp,
        knn_similarity=knn_sim,
        reason=reason_text,
    )


# ── Enrich (orchestration only — pure logic delegated to _make_*) ──
def enrich(
    conn, top_k: list[dict], kf: KeywordFilter, budget_million: int,
) -> list[RecommendationV2Item]:
    """top_k 카드 enrichment — 예상가/리스크/공급안정성/최근낙찰/전례/시각화."""
    if not top_k:
        return []

    brns = [c["brn"] for c in top_k]
    budget_won = budget_million * 1_000_000
    market = _market_baseline(conn, kf.prefix4, kf.name_regex)
    market_at_scale = _market_baseline_at_scale(conn, kf.prefix4, kf.name_regex, budget_won)
    rate_dist = _brn_rate_distribution(conn, brns)
    rate_dist_at_scale = _brn_rate_distribution_at_scale(conn, brns, budget_won)
    risks = _brn_risk_signals(conn, brns)
    awards = _brn_recent_awards(conn, brns)
    precedents = _precedents(conn, kf.prefix4, kf.name_regex, budget_won)

    # K-NN cold-start 산출물 로드 (lru_cache — 매 요청 reload X)
    knn_lookup = _load_knn_lookup()

    items: list[RecommendationV2Item] = []
    for rank_pos, c in enumerate(top_k, 1):
        brn = c["brn"]
        knn_ref = knn_lookup.get(brn) if _is_cold_or_dormant(c) else None
        ctx = CardContext(
            budget_won=budget_won,
            market=market,
            market_at_scale=market_at_scale,
            dist=rate_dist.get(brn, {}),
            dist_at_scale=rate_dist_at_scale.get(brn, {}),
            risk_signals=risks.get(brn, {}),
            awards=awards.get(brn, []),
            precedents=precedents,
            knn_ref=knn_ref,
        )
        items.append(_build_recommendation_item(rank_pos, c, ctx))
    return items


# ── KPI ─────────────────────────────────────────────────────────────
def _contract_recommend(pool_size: int) -> str:
    if pool_size <= 1:
        return "수의계약"
    if pool_size <= 5:
        return "제한경쟁"
    return "일반경쟁"


def _supply_risk(pool_size: int) -> str:
    if pool_size <= 1:
        return "높음"
    if pool_size < 10:
        return "보통"
    return "낮음"


def compute_kpi(
    conn, candidates: list[dict],
    top_k_enriched: list[RecommendationV2Item], kf: KeywordFilter,
) -> KpiV2:
    pool = len(candidates)
    sr_count = sum(1 for c in candidates if (c.get("sr_count") or 0) > 0)
    sr_pct = (100.0 * sr_count / pool) if pool else 0.0

    # 시장 깊이 — 등록 BRN 전체 (warm 한정 X)
    sql = """
    SELECT COUNT(DISTINCT mis.brn)
    FROM mart_item_supply mis
    JOIN (SELECT DISTINCT dtil_prdct_clsfc_no, dtil_prdct_clsfc_no_nm
          FROM stg_bid_notice WHERE dtil_prdct_clsfc_no_nm IS NOT NULL) inm
      USING (dtil_prdct_clsfc_no)
    WHERE LEFT(mis.dtil_prdct_clsfc_no, 4) = ANY(%s)
      AND inm.dtil_prdct_clsfc_no_nm ~ %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (kf.prefix4, kf.name_regex))
        registered = int(cur.fetchone()[0] or 0)

    prices = [t.expected_price.point_million for t in top_k_enriched
              if t.expected_price.point_million is not None]
    avg_price_million = (sum(prices) // len(prices)) if prices else None

    return KpiV2(
        pool_size=pool,
        market_depth=MarketDepth(registered=registered, env_active=pool),
        sr_count=sr_count,
        sr_pct=round(sr_pct, 1),
        avg_expected_price_million=avg_price_million,
        supply_risk=_supply_risk(pool),
        contract_recommend=_contract_recommend(pool),
    )


def _compliance(top_k_enriched: list[RecommendationV2Item]) -> ComplianceInfo:
    sr_labels = ("여성기업", "장애인기업", "사회적기업")
    sr_in = sum(
        1 for t in top_k_enriched
        if any(b in sr_labels for b in t.badges)
    )
    n = len(top_k_enriched)
    pct = (100.0 * sr_in / n) if n else 0.0
    return ComplianceInfo(
        sr_in_top_k=sr_in,
        sr_pct_top_k=round(pct, 1),
        obligation_threshold_pct=SR_LEGAL_FLOOR_PCT,
        obligation_met=pct >= SR_LEGAL_FLOOR_PCT,
    )


def _cutoff(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(fetched_at) FROM stg_award")
        row = cur.fetchone()
        return row[0].isoformat() if row and row[0] else ""


# ── Orchestrator ────────────────────────────────────────────────────
def recommend(req: RecommendV2Request, dsn: str = DEFAULT_DSN) -> RecommendV2Response:
    with _connect(dsn) as conn:
        candidates, kf = retrieve(conn, req.item_keyword, req.sr_filter)
        cutoff = _cutoff(conn)

        if not candidates:
            return RecommendV2Response(
                item_keyword=req.item_keyword,
                matched_prefix4=kf.prefix4,
                cutoff_date=cutoff,
                kpi=None,
                compliance=None,
                recommendations=[],
                meta={"warning": "후보 0건 — 정책 필터 완화 권유"},
            )

        scored = rank(
            candidates,
            context={"budget_million": req.budget_million_won},
        )
        sorted_scored = sorted(scored, key=lambda x: x["rule_score"], reverse=True)
        top_k = sorted_scored[: req.top_k]

        enriched = enrich(conn, top_k, kf, req.budget_million_won)
        kpi = compute_kpi(conn, scored, enriched, kf)
        compliance = _compliance(enriched)

    meta: dict[str, Any] = {"weights_applied": "rule"}
    if len(candidates) == 1:
        meta["warning"] = "단독공급 — 가격경쟁 어려움"

    return RecommendV2Response(
        item_keyword=req.item_keyword,
        matched_prefix4=kf.prefix4,
        cutoff_date=cutoff,
        kpi=kpi,
        compliance=compliance,
        recommendations=enriched,
        meta=meta,
    )
