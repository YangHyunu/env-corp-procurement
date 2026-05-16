"""
BRN 단위 클러스터링 학습 — pipeline.clustering.fit() 진입점.

데이터:
  - warm BRN (env_corp + env_domain 누적 거래 1+ 활성 업체)
  - 15차원 피처 (CLAUDE.md §13 / pipeline/clustering.py FEATURE_COLUMNS)

산출:
  - artifacts/clustering_artifact.pkl  (scaler+UMAP+HDBSCAN+KMeans, 운영 추론용)
  - artifacts/clustering_assignments.csv  (BRN → cluster_id, prob, umap_x/y)
  - artifacts/clustering_profiles.json   (군집별 라벨/통계)
  - artifacts/clustering_metrics.json    (silhouette/DBI)

사용:
  uv run python scripts/train_clustering.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.clustering import (  # noqa: E402
    ClusteringConfig,
    compute_metrics,
    compute_profiles,
    fit,
)

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train_clustering")

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


# ── BRN 피처 SQL ─────────────────────────────────────────────────
# 학습 단위: warm BRN (env_corp + env_domain 누적 거래 1+).
# 15 피처 — pipeline.clustering.FEATURE_COLUMNS 와 동일 순서.
SQL_BRN_FEATURES = """
WITH env_award AS (
    SELECT a.bidwinnr_brn AS brn, a.dminstt_cd, a.sucsfbid_amt, a.sucsfbid_rate,
           a.fnl_sucsf_date, b.dtil_prdct_clsfc_no
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain')
      AND a.bidwinnr_brn IS NOT NULL
      AND a.sucsfbid_rate IS NOT NULL
),
brn_supply AS (
    SELECT brn,
           COUNT(*)                              AS env_award_count_total,
           COALESCE(SUM(sucsfbid_amt), 0)::bigint AS env_award_amt_total,
           AVG(sucsfbid_rate)                    AS env_avg_rate,
           COUNT(DISTINCT dminstt_cd)            AS env_dminstt_count,
           COUNT(DISTINCT LEFT(dtil_prdct_clsfc_no, 4)) AS prefix4_diversity,
           STDDEV(sucsfbid_rate)                 AS price_volatility,
           MAX(fnl_sucsf_date)                   AS last_award_at,
           MODE() WITHIN GROUP (ORDER BY LEFT(dtil_prdct_clsfc_no, 4)) AS dominant_prefix4
    FROM env_award GROUP BY brn
),
-- 1순위 vs 최종낙찰 패턴 (탈락 비율)
brn_lost AS (
    SELECT o.winner_brn AS brn,
           COUNT(*) AS top1_cnt,
           COUNT(*) FILTER (
             WHERE a.bidwinnr_brn IS NULL OR a.bidwinnr_brn != o.winner_brn
           ) AS lost_cnt
    FROM stg_opening_result o
    LEFT JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.agency_tier IN ('env_corp', 'env_domain') AND o.winner_brn IS NOT NULL
    GROUP BY o.winner_brn
),
-- prefix4별 단가 z-score 산출용
prefix4_unit AS (
    SELECT brn,
           dominant_prefix4,
           env_award_amt_total::float / NULLIF(env_award_count_total, 0) AS unit_price
    FROM brn_supply
),
prefix4_stats AS (
    SELECT dominant_prefix4,
           AVG(unit_price) AS mu,
           STDDEV(unit_price) AS sigma
    FROM prefix4_unit GROUP BY 1
),
brn_zscore AS (
    SELECT pu.brn,
           CASE
             WHEN ps.sigma IS NULL OR ps.sigma = 0 THEN 0.0
             ELSE (pu.unit_price - ps.mu) / ps.sigma
           END AS avg_unit_price_zscore
    FROM prefix4_unit pu
    LEFT JOIN prefix4_stats ps USING (dominant_prefix4)
)
SELECT
    s.brn,
    -- A. 공급역량 (5)
    s.env_award_count_total,
    s.env_award_amt_total,
    COALESCE(s.env_avg_rate, 0)::float AS env_avg_rate,
    s.env_dminstt_count,
    EXTRACT(EPOCH FROM (NOW() - m.g2b_registered_at::timestamptz)) / (365.25*86400) AS g2b_age_years,
    -- B. 도메인 (3)
    s.prefix4_diversity,
    CASE
      WHEN m.main_dtil_prdct_cd IS NULL THEN 0
      WHEN LEFT(m.main_dtil_prdct_cd, 4) = s.dominant_prefix4 THEN 1
      ELSE 0
    END AS main_prdct_consistency,
    CASE WHEN m.is_manufacturer THEN 1 ELSE 0 END AS is_manufacturer_flag,
    -- C. SR (3)
    COALESCE(sr.sr_count, 0) AS sr_count,
    CASE WHEN COALESCE(sr.disabled_corp_flag, false)
              OR COALESCE(sr.social_corp_flag, false) THEN 1 ELSE 0 END AS real_sr_flag,
    CASE WHEN COALESCE(sr.female_ceo_flag, false) THEN 1 ELSE 0 END AS female_ceo_flag,
    -- D. 리스크 (2)
    CASE
      WHEN COALESCE(l.top1_cnt, 0) = 0 THEN 0
      ELSE l.lost_cnt::float / l.top1_cnt
    END AS bid_lost_ratio,
    EXTRACT(EPOCH FROM (NOW() - s.last_award_at::timestamptz)) / (30.4*86400) AS dormant_months,
    -- E. 가격 (2)
    z.avg_unit_price_zscore,
    COALESCE(s.price_volatility, 0)::float AS price_volatility,
    -- 프로파일용 메타 (FEATURE_COLUMNS 외)
    s.dominant_prefix4,
    m.region_code
FROM brn_supply s
LEFT JOIN mart_company_master m USING (brn)
LEFT JOIN mart_company_sr     sr USING (brn)
LEFT JOIN brn_lost l USING (brn)
LEFT JOIN brn_zscore z USING (brn);
"""


def load_data() -> pd.DataFrame:
    with psycopg2.connect(DSN) as conn:
        df = pd.read_sql(SQL_BRN_FEATURES, conn)
    logger.info("loaded %d warm BRNs × %d cols", len(df), df.shape[1])
    return df


def main() -> int:
    config = ClusteringConfig()
    df = load_data()

    if len(df) < config.hdbscan_min_cluster_size * 2:
        logger.error("too few BRNs (%d) for clustering", len(df))
        return 1

    # 1) 학습
    logger.info("="*70)
    logger.info("학습 시작 — config=%s", config.to_dict())
    logger.info("="*70)
    artifact, assignments = fit(df, config)

    # 2) 프로파일
    profiles = compute_profiles(df, assignments, config)

    # 3) 메트릭
    metrics = compute_metrics(artifact, df, assignments)

    # 4) 산출물 저장
    artifact.save(ARTIFACTS / "clustering_artifact.pkl")
    assignments.to_csv(ARTIFACTS / "clustering_assignments.csv", index=False)

    profile_dicts = [asdict(p) for p in profiles]
    with open(ARTIFACTS / "clustering_profiles.json", "w", encoding="utf-8") as f:
        json.dump(profile_dicts, f, ensure_ascii=False, indent=2)

    with open(ARTIFACTS / "clustering_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    # 5) 콘솔 리포트
    print()
    print("="*70)
    print("클러스터링 학습 결과")
    print("="*70)
    print(f"  BRN 수            : {metrics['n_brns']}")
    print(f"  피처 수           : {metrics['n_features']}")
    print(f"  군집 수           : {metrics['n_clusters']}")
    print(f"  노이즈 BRN        : {metrics['n_noise']} ({100*metrics['n_noise']/metrics['n_brns']:.1f}%)")
    if metrics['silhouette_score'] is not None:
        print(f"  Silhouette        : {metrics['silhouette_score']:.4f} (0~1, 높을수록 좋음)")
        print(f"  Davies-Bouldin    : {metrics['davies_bouldin_score']:.4f} (낮을수록 좋음)")
    print()
    print("[ 군집별 프로파일 ]")
    print(f"  {'cid':>4} {'BRN':>5} {'SR%':>6} {'avg_env':>8} {'lost%':>6}  라벨")
    print("-"*100)
    for p in profiles:
        print(
            f"  {p.cluster_id:>4} {p.brn_count:>5} {p.sr_pct:>5.1f}% "
            f"{p.avg_env_award_count:>8.1f} {p.avg_bid_lost_ratio*100:>5.1f}%  "
            f"{'★' if p.is_sr_trusted else ' '} {p.label}"
        )
    print("="*70)
    print(f"산출물 → artifacts/")
    print(f"  - clustering_artifact.pkl")
    print(f"  - clustering_assignments.csv ({len(assignments)} BRN)")
    print(f"  - clustering_profiles.json ({len(profiles)} 군집)")
    print(f"  - clustering_metrics.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
