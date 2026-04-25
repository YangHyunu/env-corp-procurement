"""
scoring.py — MVP supplier recommendation scoring (가중합 + 백분위 정규화).

설계 근거: .omc/research/research-20260425-scoring/stages/stage-4.md
공식: 4 score dims (supply_stability / sr_diversity / track_record / price_competitiveness)
      + 5 radar axes (위 4개 + risk_free 스텁 + cluster_fit 스텁)

알고리즘:
  1. fetch_pool: mart_item_supply ∩ mart_company_sr ∩ mart_company_master @ item_code
  2. hard gates (sr_filter)
  3. axis raw scores ∈ [0, 1]
  4. composite = Σ w_i · axis_i (4 active dims)
  5. SR soft floor: n_sr_certified ≥ 3 인 경우 SR=0을 -1.0 demote
  6. tiebreaker: composite > sr_count > award_count > tenure
  7. reason 템플릿
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logger = logging.getLogger(__name__)


DEFAULT_WEIGHTS: dict[str, float] = {
    "sr_diversity":          0.35,
    "track_record":          0.30,
    "price_competitiveness": 0.20,
    "supply_stability":      0.15,
}
SR_LEGAL_FLOOR = 0.20  # 사회적 가치 우선구매 촉진법 제7조


@dataclass
class SrFilter:
    require_any_sr: bool = False
    female_ceo: bool = False
    disabled_corp: bool = False
    social_corp: bool = False


@dataclass
class Recommendation:
    rank: int
    brn: str
    corp_name: str
    composite_score: float
    axes: dict[str, float]
    weighted_segments: dict[str, float]
    sr_badges: list[str]
    award_summary: dict[str, Any]
    reason: str
    is_sr_demoted: bool = False


@dataclass
class ScoreResult:
    item_code: str
    matched_count: int
    sr_coverage_pct: float
    recommendations: list[Recommendation] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


POOL_SQL = """
SELECT mis.brn,
       mis.award_count,
       mis.award_total_amt,
       mis.avg_bid_rate,
       mis.last_award_at,
       mis.supply_source,
       mcs.sr_count,
       mcs.female_ceo_flag,
       mcs.disabled_corp_flag,
       mcs.social_corp_flag,
       mcm.corp_name,
       mcm.corp_size,
       mcm.is_manufacturer,
       mcm.g2b_registered_at,
       mcm.region_code
FROM mart_item_supply mis
JOIN mart_company_sr     mcs USING (brn)
JOIN mart_company_master mcm USING (brn)
WHERE mis.dtil_prdct_clsfc_no = %s
"""


def _validate_weights(weights: dict[str, float]) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > 1e-3:
        raise ValueError(f"weights must sum to 1.0 (got {s:.4f})")
    if weights.get("sr_diversity", 0.0) < SR_LEGAL_FLOOR - 1e-3:
        raise ValueError(
            f"sr_diversity weight must be ≥ {SR_LEGAL_FLOOR} (legal floor)"
        )


def _fetch_pool(item_code: str, dsn: str) -> pd.DataFrame:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(POOL_SQL, (item_code,))
            return pd.DataFrame(cur.fetchall())


def _apply_sr_filter(pool: pd.DataFrame, f: SrFilter) -> pd.DataFrame:
    if f.require_any_sr:
        pool = pool[pool["sr_count"] > 0]
    if f.female_ceo:
        pool = pool[pool["female_ceo_flag"]]
    if f.disabled_corp:
        pool = pool[pool["disabled_corp_flag"]]
    if f.social_corp:
        pool = pool[pool["social_corp_flag"]]
    return pool


def _compute_axes(pool: pd.DataFrame) -> pd.DataFrame:
    p = pool.copy()
    n = len(p)

    # Axis 1: supply_stability — rank within pool by award_count DESC
    p["rank_award_count"] = p["award_count"].rank(method="min", ascending=False)
    p["axis_supply_stability"] = (n - p["rank_award_count"] + 1) / n
    p.loc[p["award_count"] == 0, "axis_supply_stability"] = 0.0

    # Axis 2: sr_diversity
    p["axis_sr_diversity"] = p["sr_count"].clip(0, 3).astype(float) / 3.0

    # Axis 3: track_record (count + bid_rate)
    max_count = max(p["award_count"].max() or 1, 1)
    p["norm_count"] = p["award_count"].astype(float) / max_count
    p["norm_bid_rate"] = p["avg_bid_rate"].fillna(0.0).astype(float) / 100.0
    rate_weight = p["avg_bid_rate"].notna().astype(float)
    p["axis_track_record"] = (
        0.6 * p["norm_count"] + 0.4 * p["norm_bid_rate"] * rate_weight
    ).clip(0.0, 1.0)

    # Axis 4 (radar stub): risk_free
    p["axis_risk_free"] = 1.0
    # Axis 5 (radar stub): cluster_fit
    p["axis_cluster_fit"] = 0.5

    # Score-only dim: price_competitiveness (inverse percentile of unit price)
    p["unit_price"] = (
        p["award_total_amt"].astype(float) / p["award_count"].replace(0, np.nan)
    )
    if p["unit_price"].notna().sum() >= 3:
        p["axis_price_competitiveness"] = (
            1.0 - p["unit_price"].rank(method="min", pct=True)
        ).fillna(0.5)
    else:
        p["axis_price_competitiveness"] = 0.5

    return p


def _composite(p: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    p = p.copy()
    p["composite_score"] = (
        weights["supply_stability"]      * p["axis_supply_stability"]
        + weights["sr_diversity"]        * p["axis_sr_diversity"]
        + weights["track_record"]        * p["axis_track_record"]
        + weights["price_competitiveness"] * p["axis_price_competitiveness"]
    )

    # SR soft floor: n_sr_certified ≥ 3 → demote SR=0
    n_sr_cert = int((p["sr_count"] > 0).sum())
    p["is_sr_demoted"] = False
    if n_sr_cert >= 3:
        demote_mask = p["sr_count"] == 0
        p.loc[demote_mask, "composite_score"] -= 1.0
        p.loc[demote_mask, "is_sr_demoted"] = True

    return p


def _build_reason(row: pd.Series) -> str:
    parts: list[str] = []
    if row["award_count"] > 0:
        parts.append(
            f"환경공단 낙찰 {int(row['award_count'])}건"
            f" (총 {row['award_total_amt'] / 1e8:.2f}억원)"
        )
    else:
        parts.append("환경공단 낙찰 이력 없음 (CSV 등록 공급사)")

    sr_labels: list[str] = []
    if row["female_ceo_flag"]:
        sr_labels.append("여성기업(자동판별)")
    if row["disabled_corp_flag"]:
        sr_labels.append("장애인기업")
    if row["social_corp_flag"]:
        sr_labels.append("사회적기업")
    if sr_labels:
        parts.append(", ".join(sr_labels))
    else:
        parts.append("SR 인증 없음")

    if row["axis_supply_stability"] >= 0.85 and row["award_count"] > 0:
        parts.append("이 품목 공급망 상위권")

    return " · ".join(parts)


def _to_recommendation(rank: int, row: pd.Series, weights: dict[str, float]) -> Recommendation:
    axes = {
        "supply_stability": float(row["axis_supply_stability"]),
        "sr_diversity":     float(row["axis_sr_diversity"]),
        "track_record":     float(row["axis_track_record"]),
        "risk_free":        float(row["axis_risk_free"]),     # radar stub
        "cluster_fit":      float(row["axis_cluster_fit"]),   # radar stub
    }
    weighted_segments = {
        "supply_stability":      weights["supply_stability"]      * axes["supply_stability"],
        "sr_diversity":          weights["sr_diversity"]          * axes["sr_diversity"],
        "track_record":          weights["track_record"]          * axes["track_record"],
        "price_competitiveness": weights["price_competitiveness"] * float(row["axis_price_competitiveness"]),
    }
    sr_badges: list[str] = []
    if row["female_ceo_flag"]:    sr_badges.append("여성기업(자동판별)")
    if row["disabled_corp_flag"]: sr_badges.append("장애인기업")
    if row["social_corp_flag"]:   sr_badges.append("사회적기업")

    return Recommendation(
        rank=rank,
        brn=row["brn"],
        corp_name=row["corp_name"],
        composite_score=float(max(row["composite_score"], 0.0)),  # clamp display
        axes=axes,
        weighted_segments=weighted_segments,
        sr_badges=sr_badges,
        award_summary={
            "count":       int(row["award_count"]),
            "total_amt":   int(row["award_total_amt"]),
            "avg_rate":    None if pd.isna(row["avg_bid_rate"]) else float(row["avg_bid_rate"]),
            "last_award_at": None if pd.isna(row["last_award_at"]) else row["last_award_at"].isoformat(),
            "supply_source": row["supply_source"],
        },
        reason=_build_reason(row),
        is_sr_demoted=bool(row["is_sr_demoted"]),
    )


def score(
    item_code: str,
    *,
    weights: dict[str, float] | None = None,
    sr_filter: SrFilter | None = None,
    top_k: int = 5,
    dsn: str = DEFAULT_DSN,
) -> ScoreResult:
    """Top-K 추천 + 메타. stage-4 spec 그대로."""
    weights = weights or DEFAULT_WEIGHTS
    _validate_weights(weights)

    pool = _fetch_pool(item_code, dsn)
    if pool.empty:
        return ScoreResult(
            item_code=item_code,
            matched_count=0,
            sr_coverage_pct=0.0,
            meta={"error": "ITEM_NOT_FOUND"},
        )

    if sr_filter:
        pool = _apply_sr_filter(pool, sr_filter)
    if pool.empty:
        return ScoreResult(
            item_code=item_code,
            matched_count=0,
            sr_coverage_pct=0.0,
            meta={"warning": "SR 필터로 모든 후보 제외 — 필터 완화 필요"},
        )

    pool = _compute_axes(pool)
    pool = _composite(pool, weights)

    pool = pool.sort_values(
        by=["composite_score", "sr_count", "award_count", "g2b_registered_at"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    n = len(pool)
    n_sr_cert = int((pool["sr_count"] > 0).sum())
    sr_coverage_pct = 100.0 * n_sr_cert / n
    only_one = (n == 1)
    meta: dict[str, Any] = {
        "risk_free_stub": True,
        "cluster_stub":   True,
        "sr_floor_active": n_sr_cert >= 3,
        "weights_applied": weights,
    }
    if only_one:
        meta["warning"] = "유일 공급사"

    recs: list[Recommendation] = []
    for i, row in pool.head(top_k).iterrows():
        recs.append(_to_recommendation(int(i) + 1, row, weights))

    return ScoreResult(
        item_code=item_code,
        matched_count=n,
        sr_coverage_pct=sr_coverage_pct,
        recommendations=recs,
        meta=meta,
    )
