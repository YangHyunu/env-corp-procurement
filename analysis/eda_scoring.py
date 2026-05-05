"""
eda_scoring.py — Scoring 알고리즘 EDA + 팀 게이트 토의 자료.

차트 5개 + stat 5개 산출:
  1. 품목당 top-5 점수 스프레드 (동점/cold-start 비율)
  2. 풀 크기 vs 점수 차별화
  3. SR 가중치 민감도 (top-K 변동률)
  4. 품목당 SR 보유 BRN 분포 (floor 임계값 캘리브)
  5. 점수 차원 기여도 (어떤 축이 ranking을 끌고 가는지)

사용:
  uv run python analysis/eda_scoring.py
출력:
  analysis/figures/*.png + stdout stats
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.scoring import DEFAULT_WEIGHTS, score  # noqa: E402

warnings.filterwarnings("ignore")
load_dotenv(find_dotenv(usecwd=True))

DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")
FIG = Path(__file__).resolve().parent / "figures"
FIG.mkdir(exist_ok=True)

# 한글 폰트 (macOS)
matplotlib.rcParams["font.family"] = "AppleGothic"
matplotlib.rcParams["axes.unicode_minus"] = False


def _query(sql: str, params=None) -> pd.DataFrame:
    with psycopg2.connect(DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return pd.DataFrame(cur.fetchall())


# ── 데이터 로드 ─────────────────────────────────────────────
def list_env_items() -> pd.DataFrame:
    return _query("""
        SELECT b.dtil_prdct_clsfc_no AS item_code,
               MAX(b.dtil_prdct_clsfc_no_nm) AS item_name,
               COUNT(*) AS bids
        FROM stg_bid_notice b
        WHERE b.is_env_corp AND b.dtil_prdct_clsfc_no IS NOT NULL
        GROUP BY 1 ORDER BY bids DESC
    """)


def score_all_items_topk(items: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """모든 품목 top-K 결과를 long-form 데이터프레임으로."""
    rows = []
    for _, r in items.iterrows():
        try:
            res = score(r["item_code"], top_k=k)
        except Exception as e:
            print(f"[skip] {r['item_code']}: {e}")
            continue
        if not res.recommendations:
            continue
        for rec in res.recommendations:
            rows.append({
                "item_code": r["item_code"],
                "item_name": r["item_name"],
                "rank": rec.rank,
                "brn": rec.brn,
                "composite": rec.composite_score,
                "matched": res.matched_count,
                "sr_coverage_pct": res.sr_coverage_pct,
                "axis_supply":  rec.axes["supply_stability"],
                "axis_sr":      rec.axes["sr_diversity"],
                "axis_track":   rec.axes["track_record"],
                "seg_supply":   rec.weighted_segments["supply_stability"],
                "seg_sr":       rec.weighted_segments["sr_diversity"],
                "seg_track":    rec.weighted_segments["track_record"],
                "seg_price":    rec.weighted_segments["price_competitiveness"],
                "award_count":  rec.award_summary["count"],
            })
    return pd.DataFrame(rows)


# ── 차트 1: top-5 spread ─────────────────────────────────────
def chart_top5_spread(top5: pd.DataFrame) -> None:
    spread = (
        top5.groupby("item_code")
            .agg(top1=("composite", "max"),
                 top5=("composite", "min"),
                 matched=("matched", "first"))
            .assign(spread=lambda x: x["top1"] - x["top5"])
            .sort_values("spread")
    )
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    ax[0].hist(spread["spread"], bins=30, color="#3a86ff", edgecolor="white")
    ax[0].axvline(0.05, color="red", linestyle="--", label="동점 임계 (<0.05)")
    ax[0].set_xlabel("Top1 - Top5 점수 차이")
    ax[0].set_ylabel("품목 수")
    ax[0].set_title(f"품목별 Top-5 점수 스프레드 (n={len(spread)})")
    ax[0].legend()

    n_tied = int((spread["spread"] < 0.05).sum())
    n_total = len(spread)

    ax[1].scatter(spread["matched"], spread["spread"], alpha=0.5, s=20,
                  c=spread["spread"], cmap="coolwarm_r")
    ax[1].set_xlabel("풀 크기 (matched BRN 수)")
    ax[1].set_ylabel("Top1 - Top5 점수 차이")
    ax[1].set_xscale("log")
    ax[1].set_title("풀 크기 vs 점수 차별화")
    ax[1].axhline(0.05, color="red", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(FIG / "01_top5_spread.png", dpi=120)
    plt.close()
    print(f"\n[차트1] {n_tied}/{n_total} ({n_tied/n_total*100:.1f}%) "
          f"품목이 top-5 동점 (spread<0.05)")
    print(f"        median spread = {spread['spread'].median():.3f}")


# ── 차트 2: SR 가중치 민감도 ─────────────────────────────────
def chart_sr_sensitivity(item_codes: list[str], item_names: list[str]) -> None:
    """SR 가중치를 0.20 → 0.50 슬라이딩하며 top-5 변동률."""
    sr_weights = np.linspace(0.20, 0.50, 7)
    fig, axes = plt.subplots(1, len(item_codes), figsize=(5 * len(item_codes), 4),
                              sharey=True)
    if len(item_codes) == 1:
        axes = [axes]

    for ax, code, name in zip(axes, item_codes, item_names):
        # 기본 비율 (SR 제외 나머지)
        # other_total = 1 - SR; track:price:supply = 0.30:0.20:0.15 = 6:4:3 (sum 13)
        results_per_w = []
        for sr_w in sr_weights:
            other = 1.0 - sr_w
            w = {
                "sr_diversity":          sr_w,
                "track_record":          other * (6 / 13),
                "price_competitiveness": other * (4 / 13),
                "supply_stability":      other * (3 / 13),
            }
            res = score(code, weights=w, top_k=5)
            results_per_w.append({rec.brn: rec.rank for rec in res.recommendations})

        # 각 BRN의 rank trajectory
        all_brns = set()
        for r in results_per_w:
            all_brns.update(r.keys())

        for brn in all_brns:
            ranks = [r.get(brn, 6) for r in results_per_w]
            ax.plot(sr_weights, ranks, marker="o", alpha=0.5, linewidth=1)

        ax.set_xlabel("SR 가중치")
        ax.set_ylabel("Top-K 순위")
        ax.set_title(f"{name}\n(SR 0.20→0.50)")
        ax.set_ylim(5.5, 0.5)
        ax.invert_yaxis()
        ax.grid(alpha=0.3)
        ax.set_xticks(sr_weights[::2])

    plt.tight_layout()
    plt.savefig(FIG / "02_sr_sensitivity.png", dpi=120)
    plt.close()
    print(f"\n[차트2] SR 가중치 0.20→0.50 sweep 결과 → analysis/figures/02_sr_sensitivity.png")


# ── 차트 3: SR 보유 분포 (floor 임계값 캘리브) ───────────────
def chart_sr_coverage(items: pd.DataFrame) -> None:
    sql = """
    SELECT mis.dtil_prdct_clsfc_no AS item_code,
           COUNT(*) AS pool,
           SUM(CASE WHEN mcs.sr_count > 0 THEN 1 ELSE 0 END) AS sr_brn,
           SUM(CASE WHEN mcs.sr_count > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS sr_pct
    FROM mart_item_supply mis
    JOIN mart_company_sr mcs USING (brn)
    GROUP BY 1
    """
    df = _query(sql)

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    ax[0].hist(df["sr_brn"], bins=range(0, max(50, int(df["sr_brn"].max())) + 5, 2),
               color="#06a77d", edgecolor="white")
    ax[0].axvline(3, color="red", linestyle="--", label="현재 SR floor 임계 (3)")
    ax[0].axvline(5, color="orange", linestyle=":", alpha=0.7, label="대안 (5)")
    ax[0].axvline(10, color="purple", linestyle=":", alpha=0.7, label="대안 (10)")
    ax[0].set_xlabel("품목당 SR 인증 BRN 수")
    ax[0].set_ylabel("품목 수")
    ax[0].set_title(f"SR 보유 BRN 분포 (n={len(df)})")
    ax[0].legend()
    ax[0].set_xlim(0, 100)

    ax[1].hist(df["sr_pct"] * 100, bins=30, color="#ffbe0b", edgecolor="white")
    ax[1].set_xlabel("품목당 SR 인증 BRN 비율 (%)")
    ax[1].set_ylabel("품목 수")
    ax[1].set_title("SR 인증 비율 분포")
    plt.tight_layout()
    plt.savefig(FIG / "03_sr_coverage.png", dpi=120)
    plt.close()

    n3 = int((df["sr_brn"] >= 3).sum())
    n5 = int((df["sr_brn"] >= 5).sum())
    n10 = int((df["sr_brn"] >= 10).sum())
    print(f"\n[차트3] SR floor 활성 품목 수:")
    print(f"        임계 3  : {n3:>3d}/{len(df)} ({n3/len(df)*100:5.1f}%) ← 현재 default")
    print(f"        임계 5  : {n5:>3d}/{len(df)} ({n5/len(df)*100:5.1f}%)")
    print(f"        임계 10 : {n10:>3d}/{len(df)} ({n10/len(df)*100:5.1f}%)")


# ── 차트 4: 점수 차원 기여도 ─────────────────────────────────
def chart_axis_contribution(top5: pd.DataFrame) -> None:
    """top-1 BRN의 가중 세그먼트 평균 — 어떤 축이 ranking을 끌고 가는지."""
    top1 = top5[top5["rank"] == 1].copy()

    means = top1[["seg_supply", "seg_sr", "seg_track", "seg_price"]].mean()
    means.index = ["supply_stability\n(w=0.15)", "sr_diversity\n(w=0.35)",
                   "track_record\n(w=0.30)", "price_competitiveness\n(w=0.20)"]

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    colors = ["#3a86ff", "#06a77d", "#ff006e", "#ffbe0b"]
    ax[0].bar(means.index, means.values, color=colors, edgecolor="white")
    ax[0].set_ylabel("평균 가중 기여도 (top-1 BRN)")
    ax[0].set_title(f"점수 축별 평균 기여도 (n={len(top1)} 품목)")
    for i, v in enumerate(means.values):
        ax[0].text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=10)

    # top1 composite score 분포
    ax[1].hist(top1["composite"], bins=30, color="#8338ec", edgecolor="white")
    ax[1].axvline(top1["composite"].median(), color="red", linestyle="--",
                  label=f"median {top1['composite'].median():.2f}")
    ax[1].set_xlabel("Top-1 composite score")
    ax[1].set_ylabel("품목 수")
    ax[1].set_title("품목별 Top-1 점수 분포")
    ax[1].legend()
    plt.tight_layout()
    plt.savefig(FIG / "04_axis_contribution.png", dpi=120)
    plt.close()
    print(f"\n[차트4] Top-1 평균 가중 기여:")
    for k, v in means.items():
        print(f"        {k.split(chr(10))[0]:<22} {v:.3f}")
    print(f"        Top-1 composite median = {top1['composite'].median():.3f}")


# ── 차트 5: cold-start 비율 (axis_track == 0) ────────────────
def chart_cold_start(top5: pd.DataFrame) -> None:
    """top-1이 award 0인 품목 비율 = cold-start zone."""
    top1 = top5[top5["rank"] == 1].copy()
    cold = top1[top1["award_count"] == 0]
    warm = top1[top1["award_count"] > 0]

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    ax[0].pie(
        [len(cold), len(warm)],
        labels=[f"Cold (award=0)\nn={len(cold)}",
                f"Warm (award≥1)\nn={len(warm)}"],
        colors=["#ff006e", "#06a77d"],
        autopct="%1.1f%%", startangle=90,
    )
    ax[0].set_title(f"품목 top-1 cold/warm 분포 (총 {len(top1)})")

    # award_count 분포 (top-1만)
    counts = top1["award_count"].value_counts().sort_index()
    ax[1].bar(counts.index.astype(str), counts.values, color="#3a86ff")
    ax[1].set_xlabel("Top-1 BRN의 award_count")
    ax[1].set_ylabel("품목 수")
    ax[1].set_title("Top-1 BRN의 환경공단 낙찰 건수 분포")
    plt.tight_layout()
    plt.savefig(FIG / "05_cold_start.png", dpi=120)
    plt.close()

    print(f"\n[차트5] Top-1 BRN 분포:")
    print(f"        cold (award=0) : {len(cold):>3d} 품목 ({len(cold)/len(top1)*100:.1f}%)")
    print(f"        warm (award≥1) : {len(warm):>3d} 품목 ({len(warm)/len(top1)*100:.1f}%)")
    print(f"        award_count 1-5: {len(top1[(top1['award_count'] >= 1) & (top1['award_count'] <= 5)])}")


def main() -> int:
    print("─" * 70)
    print("EDA: pipeline.scoring 검증 + 팀 게이트 토의 자료")
    print(f"DEFAULT_WEIGHTS = {DEFAULT_WEIGHTS}")
    print("─" * 70)

    items = list_env_items()
    print(f"환경공단 1년치 발주 품목: {len(items)}")

    print("\n전 품목 top-5 스코어링 중...")
    top5 = score_all_items_topk(items, k=5)
    print(f"  → {top5['item_code'].nunique()} 품목 / {len(top5)} 행")

    chart_top5_spread(top5)
    chart_sr_sensitivity(
        item_codes=["4015151301", "3010990401", "2611170403"],
        item_names=["수중펌프", "순환골재", "전기차충전장치"],
    )
    chart_sr_coverage(items)
    chart_axis_contribution(top5)
    chart_cold_start(top5)

    print("\n" + "─" * 70)
    print(f"✓ 차트 5개 saved: analysis/figures/")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
