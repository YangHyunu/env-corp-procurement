"""
Ranker Protocol + 구현체 — Stage 2 (Rank) swap point.

(A) RuleRanker — 4축 가중합 (현재)
(B) LGBMRanker — synthetic bid 기반 LGBM (향후, 미구현)

candidates 는 dict list. 필수 키:
  brn, sr_count, female_ceo_flag, disabled_corp_flag, social_corp_flag,
  award_count, award_total_amt, avg_bid_rate
"""
from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import pandas as pd

from pipeline.policy import SR_LEGAL_FLOOR_FRACTION


DEFAULT_WEIGHTS: dict[str, float] = {
    "sr_diversity":          0.35,
    "track_record":          0.30,
    "price_competitiveness": 0.20,
    "supply_stability":      0.15,
}


# 클러스터 라벨 → 4축 가중치 보정 (합=0 유지, 절대값 ≤ 0.15)
# 라벨 텍스트는 pipeline.clustering._label_cluster 산출과 부합하는 키워드로 매칭.
def _cluster_weight_delta(cluster_label: str | None) -> dict[str, float]:
    """cluster_label → 4축 가중치 delta. None / 미인식이면 영행렬."""
    zero = {"sr_diversity": 0.0, "track_record": 0.0,
            "price_competitiveness": 0.0, "supply_stability": 0.0}
    if not cluster_label:
        return zero
    label = cluster_label
    # "환경공단 주력 공급사" — supply +0.10, track_record -0.10
    if "환경공단 주력" in label:
        return {"sr_diversity": 0.0, "track_record": -0.10,
                "price_competitiveness": 0.0, "supply_stability": 0.10}
    # real_sr / 장애인·사회적기업 — sr +0.10, price -0.10
    if "장애인·사회적기업" in label or "장애인" in label or "사회적기업" in label:
        return {"sr_diversity": 0.10, "track_record": 0.0,
                "price_competitiveness": -0.10, "supply_stability": 0.0}
    # dormant / 활동중단 — supply -0.10, sr -0.05, price +0.15
    if "무낙찰" in label or "활동중단" in label or "분류외" in label:
        return {"sr_diversity": -0.05, "track_record": 0.0,
                "price_competitiveness": 0.15, "supply_stability": -0.10}
    return zero


def _apply_cluster_adjustment(
    base_weights: dict[str, float], cluster_label: str | None,
) -> dict[str, float]:
    """기본 가중치 + 클러스터 보정 → 새 가중치 (합=1.0 유지)."""
    delta = _cluster_weight_delta(cluster_label)
    adjusted = {k: base_weights[k] + delta[k] for k in base_weights}
    # SR 법정 하한 floor
    if adjusted["sr_diversity"] < SR_LEGAL_FLOOR_FRACTION:
        adjusted["sr_diversity"] = SR_LEGAL_FLOOR_FRACTION
    # 음수 방지
    for k in adjusted:
        if adjusted[k] < 0.0:
            adjusted[k] = 0.0
    # 재정규화 (합=1.0)
    s = sum(adjusted.values())
    if s > 0:
        adjusted = {k: v / s for k, v in adjusted.items()}
    return adjusted


class Ranker(Protocol):
    """Stage 2 ranker 인터페이스 — RuleRanker / 향후 LGBMRanker 둘 다 구현."""
    def score(
        self,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        cluster_labels: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """후보별 점수 매김. 입력 dict 에 rule_score / axes / is_sr_demoted /
        score_used 추가해 반환. cluster_labels (BRN→label) 가 주어지면 가중치 보정."""
        ...


def _validate_weights(weights: dict[str, float]) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > 1e-3:
        raise ValueError(f"weights must sum to 1.0 (got {s:.4f})")
    if weights.get("sr_diversity", 0.0) < SR_LEGAL_FLOOR_FRACTION - 1e-3:
        raise ValueError(
            f"sr_diversity weight must be ≥ {SR_LEGAL_FLOOR_FRACTION} (legal floor)"
        )


class RuleRanker:
    """4축 가중합 — pipeline.scoring 의 v1 로직 이식."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS
        _validate_weights(self.weights)

    def score(
        self,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        cluster_labels: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """후보 점수 계산.

        cluster_labels: {brn → cluster_label} dict. 주어지면 BRN별 가중치를
        클러스터 라벨에 따라 조정 (합=1.0 유지). None이면 default_weights 단일 사용.
        """
        if not candidates:
            return []

        df = pd.DataFrame(candidates).copy()
        n = len(df)
        cluster_labels = cluster_labels or {}

        # Axis 1: supply_stability — pool 내 award_count 백분위
        df["rank_award_count"] = df["award_count"].rank(method="min", ascending=False)
        df["axis_supply_stability"] = (n - df["rank_award_count"] + 1) / n
        df.loc[df["award_count"] == 0, "axis_supply_stability"] = 0.0

        # Axis 2: sr_diversity — 0~3 인증 수 / 3
        df["axis_sr_diversity"] = df["sr_count"].clip(0, 3).astype(float) / 3.0

        # Axis 3: track_record — count + bid_rate 가중합
        max_count = max(int(df["award_count"].max() or 1), 1)
        norm_count = df["award_count"].astype(float) / max_count
        norm_bid_rate = df["avg_bid_rate"].fillna(0.0).astype(float) / 100.0
        rate_weight = df["avg_bid_rate"].notna().astype(float)
        df["axis_track_record"] = (
            0.6 * norm_count + 0.4 * norm_bid_rate * rate_weight
        ).clip(0.0, 1.0)

        # Axis 4: price_competitiveness — 단가(award_total_amt / count) 역백분위
        unit_price = (
            df["award_total_amt"].astype(float)
            / df["award_count"].replace(0, np.nan)
        )
        if unit_price.notna().sum() >= 3:
            df["axis_price_competitiveness"] = (
                1.0 - unit_price.rank(method="min", pct=True)
            ).fillna(0.5)
        else:
            df["axis_price_competitiveness"] = 0.5

        # 가중합 — BRN별 클러스터 라벨로 가중치 조정 (없으면 default)
        # 성능: cluster_labels 비어있으면 단일 가중치 fast-path
        if cluster_labels:
            brn_to_label = cluster_labels
            adjusted_per_row = df["brn"].astype(str).map(
                lambda b: _apply_cluster_adjustment(self.weights, brn_to_label.get(b))
            )
            df["composite_score"] = [
                (w["supply_stability"]      * row["axis_supply_stability"]
                 + w["sr_diversity"]        * row["axis_sr_diversity"]
                 + w["track_record"]        * row["axis_track_record"]
                 + w["price_competitiveness"] * row["axis_price_competitiveness"])
                for w, (_, row) in zip(adjusted_per_row, df.iterrows())
            ]
        else:
            w = self.weights
            df["composite_score"] = (
                w["supply_stability"]      * df["axis_supply_stability"]
                + w["sr_diversity"]        * df["axis_sr_diversity"]
                + w["track_record"]        * df["axis_track_record"]
                + w["price_competitiveness"] * df["axis_price_competitiveness"]
            )

        # SR soft floor — n_sr_certified ≥ 3 일 때 sr_count=0 demote
        n_sr_cert = int((df["sr_count"] > 0).sum())
        df["is_sr_demoted"] = False
        if n_sr_cert >= 3:
            demote_mask = df["sr_count"] == 0
            df.loc[demote_mask, "composite_score"] -= 1.0
            df.loc[demote_mask, "is_sr_demoted"] = True

        # 결과를 candidates 에 머지해 반환
        out: list[dict[str, Any]] = []
        for cand, (_, row) in zip(candidates, df.iterrows()):
            out.append({
                **cand,
                "rule_score": float(max(row["composite_score"], 0.0)),
                "axes": {
                    "supply_stability":      float(row["axis_supply_stability"]),
                    "sr_diversity":          float(row["axis_sr_diversity"]),
                    "track_record":          float(row["axis_track_record"]),
                    "price_competitiveness": float(row["axis_price_competitiveness"]),
                },
                "is_sr_demoted": bool(row["is_sr_demoted"]),
                "score_used": "rule",
            })
        return out
