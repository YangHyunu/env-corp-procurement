"""
사전탐색 모드 v2 — Two-Stage 추천 오케스트레이션.

  Stage 1 (retrieve): 키워드+정책 → 후보 BRN 풀
  Stage 2 (rank):     RuleRanker (또는 향후 LGBMRanker) 점수
  Enrich:             카드 디테일 (예상가/리스크/전례/시각화)

진입점: recommend(req)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

from pipeline.item_keywords import KeywordFilter, resolve as resolve_keyword
from pipeline.ranker import Ranker, RuleRanker

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")


@dataclass
class RecommendV2Request:
    item_keyword: str
    budget_million_won: int
    sr_filter: dict[str, bool]      # {social_corp, female_ceo, disabled_corp}
    top_k: int = 5


# ── Stage 1: Retrieve ───────────────────────────────────────────────
RETRIEVE_SQL = """
WITH item_name_map AS (
  SELECT DISTINCT dtil_prdct_clsfc_no, dtil_prdct_clsfc_no_nm
  FROM stg_bid_notice WHERE dtil_prdct_clsfc_no_nm IS NOT NULL
),
warm_brns AS (
  SELECT DISTINCT bidwinnr_brn AS brn FROM stg_award a
  JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
  WHERE b.is_env_corp AND a.bidwinnr_brn IS NOT NULL
),
candidate_brns AS (
  SELECT DISTINCT mis.brn
  FROM mart_item_supply mis
  JOIN item_name_map inm USING (dtil_prdct_clsfc_no)
  JOIN warm_brns wb ON wb.brn = mis.brn
  WHERE LEFT(mis.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
    AND inm.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
),
brn_env_stats AS (
  SELECT a.bidwinnr_brn AS brn,
         COUNT(*) AS award_count,
         COALESCE(SUM(a.sucsfbid_amt), 0) AS award_total_amt,
         AVG(a.sucsfbid_rate) AS avg_bid_rate,
         MAX(a.fnl_sucsf_date) AS last_award_at
  FROM stg_award a
  JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
  WHERE b.is_env_corp AND a.bidwinnr_brn IS NOT NULL
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


def _build_sr_clause(sr_filter: dict) -> str:
    parts: list[str] = []
    if sr_filter.get("female_ceo"):    parts.append("AND mcs.female_ceo_flag")
    if sr_filter.get("disabled_corp"): parts.append("AND mcs.disabled_corp_flag")
    if sr_filter.get("social_corp"):   parts.append("AND mcs.social_corp_flag")
    return " ".join(parts)


def retrieve(
    keyword: str, sr_filter: dict, dsn: str = DEFAULT_DSN,
) -> tuple[list[dict], KeywordFilter]:
    kf = resolve_keyword(keyword)
    sql = RETRIEVE_SQL.format(sr_clause=_build_sr_clause(sr_filter))
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"prefix4": kf.prefix4, "name_regex": kf.name_regex})
            rows = [dict(r) for r in cur.fetchall()]
    return rows, kf


# ── Stage 2: Rank ───────────────────────────────────────────────────
def rank(
    candidates: list[dict], context: dict, ranker: Optional[Ranker] = None,
) -> list[dict]:
    return (ranker or RuleRanker()).score(candidates, context)


# ── Enrich helpers ──────────────────────────────────────────────────
def _market_baseline(prefix4: list[str], name_regex: str, dsn: str) -> dict:
    sql = """
    SELECT
      COUNT(*) AS n,
      AVG(a.sucsfbid_rate)  AS mean,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q25,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.sucsfbid_rate) AS q75,
      STDDEV(a.sucsfbid_rate) AS std
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.is_env_corp
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%(prefix4)s)
      AND b.dtil_prdct_clsfc_no_nm ~ %(name_regex)s
      AND a.sucsfbid_rate IS NOT NULL
    """
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"prefix4": prefix4, "name_regex": name_regex})
            r = cur.fetchone() or {}
    return {
        "n": int(r.get("n") or 0),
        "mean": float(r["mean"]) if r.get("mean") is not None else None,
        "q25":  float(r["q25"])  if r.get("q25")  is not None else None,
        "q75":  float(r["q75"])  if r.get("q75")  is not None else None,
        "std":  float(r["std"])  if r.get("std")  is not None else None,
    }


def _brn_rate_distribution(brns: list[str], dsn: str) -> dict[str, dict]:
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
    WHERE b.is_env_corp
      AND a.bidwinnr_brn = ANY(%s)
      AND a.sucsfbid_rate IS NOT NULL
    GROUP BY 1
    """
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (brns,))
            return {r["brn"]: dict(r) for r in cur.fetchall()}


def _brn_risk_signals(brns: list[str], dsn: str) -> dict[str, dict]:
    if not brns:
        return {}
    sql = """
    WITH top1 AS (
      SELECT o.winner_brn AS brn, o.bid_ntce_no, o.bid_ntce_ord, o.openg_dt,
             a.bidwinnr_brn AS final_brn
      FROM stg_opening_result o
      LEFT JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
      JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
      WHERE b.is_env_corp AND o.winner_brn IS NOT NULL AND o.rbid_no='000'
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
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (brns,))
            return {r["brn"]: dict(r) for r in cur.fetchall()}


def _brn_recent_awards(brns: list[str], dsn: str, n: int = 5) -> dict[str, list[dict]]:
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
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (brns, n))
            for row in cur.fetchall():
                out.setdefault(row["brn"], []).append(
                    {k: v for k, v in row.items() if k != "brn"}
                )
    return out


def _precedents(
    prefix4: list[str], name_regex: str, budget_won: int, dsn: str, n: int = 5,
) -> list[dict]:
    sql = """
    SELECT b.bid_ntce_no, b.bid_ntce_nm,
           a.fnl_sucsf_date::text AS fnl_sucsf_date,
           a.sucsfbid_amt,
           a.bidwinnr_brn,
           a.bidwinnr_nm AS winner_corp_name
    FROM stg_bid_notice b
    JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.is_env_corp
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = ANY(%s)
      AND b.dtil_prdct_clsfc_no_nm ~ %s
      AND a.sucsfbid_amt BETWEEN %s AND %s
    ORDER BY a.fnl_sucsf_date DESC NULLS LAST
    LIMIT %s
    """
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sql,
                (prefix4, name_regex,
                 int(budget_won * 0.5), int(budget_won * 1.5), n),
            )
            return [dict(r) for r in cur.fetchall()]


# ── Risk grade / Tier / Helpers ─────────────────────────────────────
def _risk_grade(top1: int, lost: int, recent_lost: int) -> str:
    if top1 == 0:
        return "미확인"
    ratio = lost / top1
    if lost >= 3 or ratio >= 0.30 or recent_lost >= 2:
        return "주의"
    if top1 >= 3 and lost == 0:
        return "안전"
    return "양호"


def _tier(rule_score: float, risk_grade: str) -> str:
    if risk_grade == "주의":
        return "C"
    if rule_score >= 0.6:
        return "A"
    if rule_score >= 0.3:
        return "B"
    return "C"


def _dormant_months(last_award_at) -> Optional[int]:
    if not last_award_at:
        return None
    if hasattr(last_award_at, "tzinfo") and last_award_at.tzinfo:
        diff = datetime.now(timezone.utc) - last_award_at
    else:
        diff = datetime.now() - datetime.combine(last_award_at, datetime.min.time())
    return int(diff.days / 30.4)


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
    if c.get("female_ceo_flag"):    out.append("여성기업")
    if c.get("disabled_corp_flag"): out.append("장애인기업")
    if c.get("social_corp_flag"):   out.append("사회적기업")
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
    if c.get("female_ceo_flag"):    sr_labels.append("여성")
    if c.get("disabled_corp_flag"): sr_labels.append("장애인")
    if c.get("social_corp_flag"):   sr_labels.append("사회적")
    if sr_labels:
        parts.append("+".join(sr_labels) + "기업 가점")
    return " · ".join(parts)


# ── Enrich ─────────────────────────────────────────────────────────
def enrich(
    top_k: list[dict], kf: KeywordFilter, budget_million: int, dsn: str,
) -> list[dict]:
    """top_k 카드 enrichment — 예상가/리스크/공급안정성/최근낙찰/전례/시각화."""
    if not top_k:
        return []

    brns = [c["brn"] for c in top_k]
    market = _market_baseline(kf.prefix4, kf.name_regex, dsn)
    rate_dist = _brn_rate_distribution(brns, dsn)
    risks = _brn_risk_signals(brns, dsn)
    awards = _brn_recent_awards(brns, dsn)
    budget_won = budget_million * 1_000_000
    precedents = _precedents(kf.prefix4, kf.name_regex, budget_won, dsn)

    out: list[dict] = []
    for rank_pos, c in enumerate(top_k, 1):
        brn = c["brn"]
        dist = rate_dist.get(brn, {})
        n_samples = int(dist.get("n") or 0)

        # 예상가 점추정
        if n_samples >= 1 and dist.get("mean") is not None:
            point = int(budget_won * float(dist["mean"]) / 100.0)
        elif market.get("mean") is not None:
            point = int(budget_won * market["mean"] / 100.0)
        else:
            point = budget_won  # last fallback

        # 구간/안정성/시장편차 (n>=3 일 때만)
        if n_samples >= 3 and dist.get("q25") is not None:
            q25 = int(budget_won * float(dist["q25"]) / 100.0)
            q75 = int(budget_won * float(dist["q75"]) / 100.0)
            sigma = float(dist["std"]) if dist.get("std") is not None else None
            market_diff_pp = (
                float(dist["mean"]) - market["mean"]
                if market.get("mean") is not None else None
            )
        else:
            q25 = q75 = sigma = market_diff_pp = None

        expected_price = {
            "point":          point,
            "point_million":  round(point / 1_000_000),
            "q25":            q25,
            "q75":            q75,
            "q25_million":    round(q25 / 1_000_000) if q25 is not None else None,
            "q75_million":    round(q75 / 1_000_000) if q75 is not None else None,
            "sigma_pp":       round(sigma, 2) if sigma is not None else None,
            "market_diff_pp": round(market_diff_pp, 2) if market_diff_pp is not None else None,
            "n_samples":      n_samples,
        }

        # 리스크
        rs = risks.get(brn, {})
        top1 = int(rs.get("top1_count") or 0)
        lost = int(rs.get("lost_count") or 0)
        recent = int(rs.get("recent_lost") or 0)
        ratio = (lost / top1) if top1 else 0.0
        grade = _risk_grade(top1, lost, recent)
        dormant = _dormant_months(c.get("last_award_at"))

        risk_info = {
            "grade":          grade,
            "top1_count":     top1,
            "lost_count":     lost,
            "lost_ratio":     round(ratio, 3),
            "recent_lost":    recent,
            "dormant_months": dormant,
            "is_dormant":     bool(dormant is not None and dormant >= 24),
        }

        # 공급 안정성
        g2b_age = None
        reg = c.get("g2b_registered_at")
        if reg:
            try:
                g2b_age = round(
                    (datetime.now().date() - reg).days / 365.25, 1
                )
            except Exception:
                pass

        supply_stability = {
            "g2b_age_years":   g2b_age,
            "award_total_amt": int(c.get("award_total_amt") or 0),
            "is_manufacturer": bool(c.get("is_manufacturer")),
            "last_award_at":   c["last_award_at"].isoformat() if c.get("last_award_at") else None,
        }

        # 시각화 raw
        rates = list(dist.get("rates") or [])
        amts = list(dist.get("amts") or [])
        charts = {
            "bid_rate_distribution": [float(r) for r in rates],
            "bid_amt_distribution":  [int(a) for a in amts],
        }

        out.append({
            "rank":             rank_pos,
            "brn":              brn,
            "corp_name":        c.get("corp_name"),
            "tier":             _tier(c["rule_score"], grade),
            "badges":           _badges(c),
            "summary_stats": {
                "award_count":  int(c.get("award_count") or 0),
                "avg_bid_rate": float(c["avg_bid_rate"]) if c.get("avg_bid_rate") is not None else None,
                "last_award_at": c["last_award_at"].isoformat() if c.get("last_award_at") else None,
                "lost_count":   lost,
            },
            "expected_price":   expected_price,
            "risk":             risk_info,
            "supply_stability": supply_stability,
            "recent_awards":    awards.get(brn, []),
            "precedents":       precedents,
            "charts":           charts,
            "rule_score":       float(c["rule_score"]),
            "ml_score":         None,
            "score_used":       "rule",
            "reason":           _reason(c, market.get("mean")),
        })
    return out


# ── KPI ─────────────────────────────────────────────────────────────
def _contract_recommend(pool_size: int) -> str:
    if pool_size <= 1: return "수의계약"
    if pool_size <= 5: return "제한경쟁"
    return "일반경쟁"


def _supply_risk(pool_size: int) -> str:
    if pool_size <= 1:  return "높음"
    if pool_size < 10:  return "보통"
    return "낮음"


def compute_kpi(
    candidates: list[dict], top_k_enriched: list[dict],
    kf: KeywordFilter, dsn: str,
) -> dict:
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
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (kf.prefix4, kf.name_regex))
            registered = int(cur.fetchone()[0] or 0)

    # 평균 예상가 (top_k 평균)
    avg_price_million = None
    prices = [
        t.get("expected_price", {}).get("point_million")
        for t in top_k_enriched
    ]
    prices = [p for p in prices if p is not None]
    if prices:
        avg_price_million = sum(prices) // len(prices)

    return {
        "pool_size": pool,
        "market_depth": {
            "registered": registered,
            "env_active": pool,
        },
        "sr_count": sr_count,
        "sr_pct":   round(sr_pct, 1),
        "avg_expected_price_million": avg_price_million,
        "supply_risk":         _supply_risk(pool),
        "contract_recommend":  _contract_recommend(pool),
    }


def _compliance(top_k_enriched: list[dict]) -> dict:
    sr_in = sum(
        1 for t in top_k_enriched
        if any(b in ("여성기업", "장애인기업", "사회적기업") for b in t.get("badges", []))
    )
    n = len(top_k_enriched)
    pct = (100.0 * sr_in / n) if n else 0.0
    return {
        "sr_in_top_k":            sr_in,
        "sr_pct_top_k":           round(pct, 1),
        "obligation_threshold_pct": 20.0,
        "obligation_met":         pct >= 20.0,
    }


def _cutoff(dsn: str) -> str:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(fetched_at) FROM stg_award")
            row = cur.fetchone()
            return row[0].isoformat() if row and row[0] else ""


# ── Orchestrator ────────────────────────────────────────────────────
def recommend(req: RecommendV2Request, dsn: str = DEFAULT_DSN) -> dict[str, Any]:
    candidates, kf = retrieve(req.item_keyword, req.sr_filter, dsn)

    if not candidates:
        return {
            "item_keyword":    req.item_keyword,
            "matched_prefix4": kf.prefix4,
            "cutoff_date":     _cutoff(dsn),
            "kpi":             None,
            "compliance":      None,
            "recommendations": [],
            "meta": {"warning": "후보 0건 — 정책 필터 완화 권유"},
        }

    scored = rank(candidates, context={"budget_million": req.budget_million_won})
    sorted_scored = sorted(scored, key=lambda x: x["rule_score"], reverse=True)
    top_k = sorted_scored[: req.top_k]

    enriched = enrich(top_k, kf, req.budget_million_won, dsn)
    kpi = compute_kpi(scored, enriched, kf, dsn)
    compliance = _compliance(enriched)

    meta: dict[str, Any] = {"weights_applied": "rule"}
    if len(candidates) == 1:
        meta["warning"] = "단독공급 — 가격경쟁 어려움"

    return {
        "item_keyword":    req.item_keyword,
        "matched_prefix4": kf.prefix4,
        "cutoff_date":     _cutoff(dsn),
        "kpi":             kpi,
        "compliance":      compliance,
        "recommendations": enriched,
        "meta":            meta,
    }
