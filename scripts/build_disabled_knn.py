"""
장애인기업 cold-start 추천 — K-NN 유사도 기반 잠재력 풀 발굴.

목적
----
환경공단 거래 0건이지만 "잘 납품하는 회사" (cid3+cid4 주력 218곳) 와 피처가 유사한
장애인기업을 K-NN 으로 발굴해, SR 의무비율 충족에 활용 가능한 cold-start 후보 풀을 만든다.

설계 (확장판 — main_dtil_prdct_cd 활용)
----
1. Reference 풀  = mart_company_master 에서 main_dtil_prdct_cd LEFT(4) IN 환경공단 핵심 8개
                   AND disabled_corp_flag = false  → ≈ 30,168곳
                   ※ main_dtil_prdct_cd 는 G2B 가 실거래로 부여한 대표 품명 (61% non-null,
                     환경공단 낙찰자 1,650 중 1,627곳 보유 = 99% → 거래 검증된 신호)
                   ※ "공공기관 어디서든 그 도메인에서 검증된 회사" 풀로 사용
2. Target    풀  = mart_company_sr.disabled_corp_flag=true 인 BRN 전체 (~6,308곳)
                   + 환경공단 핵심 8개 prefix4 등록 필터 (~265곳)
3. 피처 (환경공단 의존성 배제 — cold-start 가능):
     A. prefix4_main   one-hot 9 (핵심 8개 + 기타)
     B. region_code    one-hot 18 (17 시도 + 미상)
     C. is_manufacturer bool 1
     D. g2b_age_years  numeric 1
     E. sr_count       numeric 1
   = 30 차원
4. 표준화 = StandardScaler.
5. K-NN = NearestNeighbors(k=5, metric='euclidean').  fit on reference, query on target.
6. similarity = 1 / (1 + mean(top3 distance))   ∈ (0, 1].
7. 산출: artifacts/disabled_knn_candidates.csv, .json (top-50 + 매칭 도메인 분포)

CLAUDE.md §9 준수:
- 새 라이브러리 X (sklearn 이미 ml extra)
- 학습 모집단 변경 X (clustering 재학습 X — 산출물만 활용)
- BRN 정규화 X 가정 (mart_* 는 이미 정규화됨)

사용
----
  uv run python scripts/build_disabled_knn.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.clustering import PREFIX4_LABEL, REGION_LABEL  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("disabled_knn")

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

ENV_CORE_PREFIX4 = ["1214", "1216", "2410", "3010", "3912", "4015", "4111", "4710"]


# ── BRN 피처 산출 ─────────────────────────────────────────────────
SQL_FEATURES = """
SELECT
    m.brn,
    m.corp_name,
    LEFT(m.main_dtil_prdct_cd, 4) AS prefix4,
    m.region_code,
    m.is_manufacturer,
    CASE WHEN m.g2b_registered_at IS NULL THEN NULL
         ELSE EXTRACT(EPOCH FROM (NOW() - m.g2b_registered_at::timestamptz)) / (365.25*86400)
    END AS g2b_age_years,
    COALESCE(sr.sr_count, 0) AS sr_count,
    COALESCE(sr.disabled_corp_flag, false) AS disabled_corp_flag,
    COALESCE(sr.social_corp_flag,   false) AS social_corp_flag,
    COALESCE(sr.female_ceo_flag,    false) AS female_ceo_flag
FROM mart_company_master m
LEFT JOIN mart_company_sr sr USING (brn)
WHERE m.brn = ANY(%(brns)s);
"""


def load_features(conn, brns: list[str]) -> pd.DataFrame:
    df = pd.read_sql(SQL_FEATURES, conn, params={"brns": brns})
    logger.info("loaded %d × %d feature rows", len(df), df.shape[1])
    return df


def build_feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """카테고리 one-hot + numeric 정규화 → (n, 30) 행렬."""
    from sklearn.preprocessing import StandardScaler

    # prefix4: 핵심 8개 + 기타 + 결측
    df = df.copy()
    df["prefix4_main"] = df["prefix4"].apply(
        lambda p: p if p in ENV_CORE_PREFIX4 else ("기타" if p else "미상")
    )
    df["region_main"] = df["region_code"].fillna("미상")
    df["g2b_age_years"] = df["g2b_age_years"].fillna(0).astype(float)
    df["is_manufacturer_int"] = df["is_manufacturer"].astype(int)

    # one-hot
    pfx_oh = pd.get_dummies(df["prefix4_main"], prefix="pfx").astype(float)
    reg_oh = pd.get_dummies(df["region_main"], prefix="reg").astype(float)

    # numeric (sklearn StandardScaler)
    num_cols = ["is_manufacturer_int", "g2b_age_years", "sr_count"]
    num = df[num_cols].astype(float).to_numpy()
    num_scaled = StandardScaler().fit_transform(num)
    num_df = pd.DataFrame(num_scaled, columns=num_cols, index=df.index)

    feat = pd.concat([pfx_oh, reg_oh, num_df], axis=1)
    cols = list(feat.columns)
    return feat.to_numpy(), cols


def main() -> int:
    # 1) reference 풀 — 환경공단에서 1건+ 낙찰 검증된 비-장애인 BRN (≈1,592곳)
    #    "잘 납품하는 회사" 정의: 환경공단 거래 실적이 있는 곳. main_dtil_prdct_cd 만 보면
    #    등록만 한 28,500곳이 섞여서 K-NN 매칭이 비활성끼리 가버림. 거래 검증된 풀로 좁힘.
    with psycopg2.connect(DSN) as conn:
        ref_brns = pd.read_sql(
            """
            SELECT DISTINCT a.bidwinnr_brn AS brn
            FROM stg_award a
            JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
            LEFT JOIN mart_company_sr sr ON sr.brn = a.bidwinnr_brn
            WHERE b.agency_tier IN ('env_corp','env_domain')
              AND NOT COALESCE(sr.disabled_corp_flag, false);
            """,
            conn,
        )["brn"].tolist()
        logger.info("reference pool (환경공단 거래 검증, 비장애인): %d BRN", len(ref_brns))

        # 2) target 풀 — 장애인기업 + 환경공단 핵심 8개 prefix4 등록
        target_brns_all = pd.read_sql(
            "SELECT brn FROM mart_company_sr WHERE disabled_corp_flag", conn
        )["brn"].tolist()
        target_brns_filtered = pd.read_sql(
            """
            SELECT m.brn FROM mart_company_master m
            JOIN mart_company_sr sr ON sr.brn = m.brn AND sr.disabled_corp_flag
            WHERE LEFT(m.main_dtil_prdct_cd, 4) = ANY(%(p)s);
            """,
            conn, params={"p": ENV_CORE_PREFIX4}
        )["brn"].tolist()
        logger.info(
            "target pool: 장애인기업 전체 %d, 환경공단 핵심 8개 prefix4 등록 %d",
            len(target_brns_all), len(target_brns_filtered),
        )

        # 피처 한번에 로드 (reference + target 합집합)
        all_brns = list(set(ref_brns) | set(target_brns_filtered))
        df = load_features(conn, all_brns)

    # 3) 피처 행렬
    X, cols = build_feature_matrix(df)
    df = df.reset_index(drop=True)
    df["__row"] = np.arange(len(df))
    logger.info("feature matrix: %s, %d cols", X.shape, len(cols))

    # 4) reference / target 분리
    ref_mask = df["brn"].isin(ref_brns)
    tgt_mask = df["brn"].isin(target_brns_filtered) & ~ref_mask  # ref 와 중복 시 ref 우선
    X_ref = X[ref_mask.to_numpy()]
    X_tgt = X[tgt_mask.to_numpy()]
    df_ref = df[ref_mask].reset_index(drop=True)
    df_tgt = df[tgt_mask].reset_index(drop=True)
    logger.info("after split — ref=%d, tgt=%d", len(df_ref), len(df_tgt))

    # 5) K-NN
    from sklearn.neighbors import NearestNeighbors
    K = 5
    knn = NearestNeighbors(n_neighbors=K, metric="euclidean")
    knn.fit(X_ref)
    distances, indices = knn.kneighbors(X_tgt)

    # 6) similarity = 1 / (1 + mean(top3 dist))
    mean_top3 = distances[:, :3].mean(axis=1)
    similarity = 1.0 / (1.0 + mean_top3)

    # 7) reference brn name lookup
    ref_brn_arr = df_ref["brn"].to_numpy()
    ref_name_arr = df_ref["corp_name"].to_numpy()

    out_rows = []
    for i, row in df_tgt.iterrows():
        nbr_idx = indices[i]
        nbr_dist = distances[i]
        nbrs = [
            {"brn": str(ref_brn_arr[j]), "name": str(ref_name_arr[j]), "dist": float(d)}
            for j, d in zip(nbr_idx, nbr_dist)
        ]
        out_rows.append({
            "brn": row["brn"],
            "corp_name": row["corp_name"],
            "prefix4": row["prefix4"],
            "item_label": PREFIX4_LABEL.get(str(row["prefix4"]), str(row["prefix4"])),
            "region_code": row["region_code"],
            "region_label": REGION_LABEL.get(str(row["region_code"]), "지역미상"),
            "is_manufacturer": bool(row["is_manufacturer"]),
            "g2b_age_years": float(row["g2b_age_years"] or 0),
            "sr_count": int(row["sr_count"]),
            "social_corp_flag": bool(row["social_corp_flag"]),
            "female_ceo_flag": bool(row["female_ceo_flag"]),
            "similarity": float(similarity[i]),
            "mean_top3_dist": float(mean_top3[i]),
            "nearest_ref_brn":  nbrs[0]["brn"],
            "nearest_ref_name": nbrs[0]["name"],
            "nearest_ref_dist": nbrs[0]["dist"],
            "top5_neighbors":   nbrs,
        })

    out_df = pd.DataFrame(out_rows).sort_values("similarity", ascending=False).reset_index(drop=True)

    # 8) reference BRN 의 환경공단 거래이력 추가 (top1 nearest 만)
    nearest_brns = out_df["nearest_ref_brn"].unique().tolist()
    with psycopg2.connect(DSN) as conn:
        ref_stats = pd.read_sql(
            """
            SELECT a.bidwinnr_brn AS brn,
                   count(*) AS env_award_count,
                   sum(a.sucsfbid_amt)::bigint AS env_award_amt
            FROM stg_award a
            JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
            WHERE a.bidwinnr_brn = ANY(%(b)s)
              AND b.agency_tier IN ('env_corp','env_domain')
            GROUP BY 1;
            """,
            conn, params={"b": nearest_brns},
        )
    out_df = out_df.merge(
        ref_stats.rename(columns={
            "brn": "nearest_ref_brn",
            "env_award_count": "nearest_ref_env_count",
            "env_award_amt":   "nearest_ref_env_amt",
        }),
        on="nearest_ref_brn", how="left",
    )
    out_df["nearest_ref_env_count"] = out_df["nearest_ref_env_count"].fillna(0).astype(int)
    out_df["nearest_ref_env_amt"]   = out_df["nearest_ref_env_amt"].fillna(0).astype(int)

    # 9) 저장
    csv_path = ARTIFACTS / "disabled_knn_candidates.csv"
    json_path = ARTIFACTS / "disabled_knn_candidates.json"
    # CSV (top5_neighbors 컬럼만 직렬화)
    out_df_csv = out_df.copy()
    out_df_csv["top5_neighbors"] = out_df_csv["top5_neighbors"].apply(json.dumps)
    out_df_csv.to_csv(csv_path, index=False, encoding="utf-8-sig")
    out_df.to_json(json_path, orient="records", force_ascii=False, indent=2)

    # 10) 콘솔 요약
    print()
    print("=" * 90)
    print(f"K-NN 유사도 기반 잠재력 장애인기업 발굴 — Reference cid3+cid4 ({len(df_ref)}곳)")
    print("=" * 90)
    print(f"  Target 풀: 장애인기업 + 환경공단 핵심 8개 prefix4 등록 = {len(df_tgt)}곳")
    print(f"  유사도 분포: min={out_df.similarity.min():.3f} / "
          f"median={out_df.similarity.median():.3f} / max={out_df.similarity.max():.3f}")
    print()
    print("  [ Top 20 후보 ]")
    print(f"  {'rank':>4} {'sim':>5} {'BRN':<12} {'회사':<22} {'도메인':<32} {'지역':<7}  {'닮은 회사 (env)'}")
    print("  " + "-" * 130)
    for r, row in out_df.head(20).iterrows():
        env_str = f"{row['nearest_ref_env_count']}건/{row['nearest_ref_env_amt']/1e8:.1f}억"
        print(
            f"  {r+1:>4} {row['similarity']:>5.3f} {row['brn']:<12} "
            f"{(row['corp_name'] or '')[:20]:<22} "
            f"{(row['item_label'] or '')[:30]:<32} "
            f"{row['region_label']:<7}  "
            f"{(row['nearest_ref_name'] or '')[:18]} ({env_str})"
        )
    print()
    print(f"  저장 → {csv_path.relative_to(ROOT)} ({len(out_df)} rows)")
    print(f"        → {json_path.relative_to(ROOT)}")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
