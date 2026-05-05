"""
LightGBM baseline 학습 + 평가.

학습:
  - mart_features_at_bid에서 피처 로드
  - 시간 split: 2021~2024 학습, 2025~2026 테스트
  - LightGBM Classifier (binary) — class_weight='balanced'

평가:
  - AUC (전체)
  - HR@5  (Hit Rate at 5) — 추천 상위 5개 중 실제 낙찰자 포함률
  - NDCG@5 — 순위 품질
  - SR Coverage @ 5 — 상위 5개 추천 중 실질SR(disabled or social) 비율

출력:
  - artifacts/lgbm_baseline.txt (모델)
  - artifacts/metrics.json (평가)
  - 콘솔 리포트

사용:
  uv run python scripts/train_baseline.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv
from sklearn.metrics import roc_auc_score

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

# ── 시간 split ─────────────────────────────────────────────
TRAIN_END = "2024-12-31"   # 2021-04 ~ 2024-12 학습
TEST_START = "2025-01-01"  # 2025-01 ~ 2026-04 테스트


# ── 피처 로드 ──────────────────────────────────────────────
SQL_LOAD = """
SELECT * FROM mart_features_at_bid
"""

CATEGORICAL = [
    "corp_size", "region_code", "cntrct_cncls_mthd_nm",
    "bid_dminstt_cd", "bid_dtil_prdct_no",
]

# 학습에서 제외할 컬럼 (메타 / leakage 위험)
DROP_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "brn",
    "is_winner",          # target
    "cutoff_date",
    "last_synced_at",
    # participated_in_bid는 학습 단계 정보라 학습에 쓰면 leakage
    # → 일단 hard-neg 식별용으로만 (drop)
    "participated_in_bid",
]


def load_data() -> pd.DataFrame:
    with psycopg2.connect(DSN) as conn:
        df = pd.read_sql(SQL_LOAD, conn)
    logger.info("loaded %s rows × %s cols", f"{len(df):,}", df.shape[1])
    return df


def split(df: pd.DataFrame):
    train = df[df["cutoff_date"].astype(str) <= TRAIN_END].copy()
    test = df[df["cutoff_date"].astype(str) >= TEST_START].copy()
    logger.info("train=%s rows (pos %.2f%%), test=%s rows (pos %.2f%%)",
                f"{len(train):,}", 100*train["is_winner"].mean(),
                f"{len(test):,}", 100*test["is_winner"].mean())
    return train, test


BOOL_COLS = [
    "is_manufacturer", "female_ceo_flag", "disabled_corp_flag",
    "social_corp_flag", "real_sr_flag", "main_prdct_match",
]


def prep(df: pd.DataFrame):
    y = df["is_winner"].astype(int).values
    groups = df.groupby(["bid_ntce_no", "bid_ntce_ord"]).size().values  # for ranking metric
    X = df.drop(columns=DROP_COLS)
    # bool 컬럼 — psycopg2가 object로 반환 → int로 변환 (None → -1)
    for c in BOOL_COLS:
        if c in X.columns:
            X[c] = X[c].map({True: 1, False: 0}).fillna(-1).astype("int8")
    # categorical → category dtype
    for c in CATEGORICAL:
        if c in X.columns:
            X[c] = X[c].astype("category")
    return X, y, groups


# ── 평가 메트릭 ────────────────────────────────────────────
def hit_rate_at_k(df: pd.DataFrame, score_col: str, k: int = 5) -> float:
    """공고당 score top-K에 실제 winner가 포함되는 비율."""
    hits = 0
    total = 0
    for _, g in df.groupby(["bid_ntce_no", "bid_ntce_ord"]):
        if (g["is_winner"] == 1).sum() == 0:
            continue
        topk = g.nlargest(k, score_col)
        if (topk["is_winner"] == 1).sum() > 0:
            hits += 1
        total += 1
    return hits / max(total, 1)


def ndcg_at_k(df: pd.DataFrame, score_col: str, k: int = 5) -> float:
    """공고당 NDCG@K. winner 1개라 DCG = 1/log2(rank+1) if winner in topK else 0."""
    scores = []
    for _, g in df.groupby(["bid_ntce_no", "bid_ntce_ord"]):
        if (g["is_winner"] == 1).sum() == 0:
            continue
        ranked = g.sort_values(score_col, ascending=False).reset_index(drop=True)
        winner_pos = ranked.index[ranked["is_winner"] == 1].tolist()
        if winner_pos and winner_pos[0] < k:
            scores.append(1.0 / np.log2(winner_pos[0] + 2))
        else:
            scores.append(0.0)
    return float(np.mean(scores)) if scores else 0.0


def sr_coverage_at_k(df: pd.DataFrame, score_col: str, k: int = 5) -> float:
    """공고당 score top-K 중 실질SR(disabled or social) 비율 평균."""
    rates = []
    for _, g in df.groupby(["bid_ntce_no", "bid_ntce_ord"]):
        topk = g.nlargest(k, score_col)
        if len(topk) == 0:
            continue
        rates.append(topk["real_sr_flag"].mean())
    return float(np.mean(rates)) if rates else 0.0


# ── main ─────────────────────────────────────────────────
def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--neg-ratio", type=int, default=0,
                   help="positive당 negative 샘플 수 (0=비활성). 학습 데이터에만 적용, 평가는 풀 그대로")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    df = load_data()
    # bool 컬럼 캐스팅 (psycopg2 object → int)
    for c in BOOL_COLS + ["is_winner", "participated_in_bid"]:
        if c in df.columns:
            df[c] = df[c].map({True: 1, False: 0}).fillna(0).astype("int8")
    train_df, test_df = split(df)

    if args.neg_ratio > 0:
        rng = np.random.default_rng(args.seed)
        # 공고 단위로 positive 전부 + negative 샘플
        sampled = []
        for _, g in train_df.groupby(["bid_ntce_no", "bid_ntce_ord"], sort=False):
            pos = g[g["is_winner"] == 1]
            neg = g[g["is_winner"] == 0]
            if len(pos) == 0:
                continue  # 학습 의미 없음
            n_keep = min(len(neg), len(pos) * args.neg_ratio)
            if n_keep > 0:
                neg_sample = neg.sample(n=n_keep, random_state=int(rng.integers(0, 1<<31)))
                sampled.append(pd.concat([pos, neg_sample]))
            else:
                sampled.append(pos)
        train_df = pd.concat(sampled).reset_index(drop=True)
        logger.info("after neg-sampling (ratio=%d): train=%s rows (pos %.2f%%)",
                    args.neg_ratio, f"{len(train_df):,}", 100*train_df["is_winner"].mean())

    X_train, y_train, _ = prep(train_df)
    X_test,  y_test,  _ = prep(test_df)

    # 클래스 비율 (~3.6%) → balanced weight
    pos_w = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    logger.info("scale_pos_weight=%.2f", pos_w)

    cat_features = [c for c in CATEGORICAL if c in X_train.columns]

    model = lgb.LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=-1,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=0.1,
        scale_pos_weight=pos_w,
        objective="binary",
        metric="auc",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    logger.info("training...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="auc",
        categorical_feature=cat_features,
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
    )

    # 예측 + 메트릭
    test_df = test_df.copy()
    test_df["score"] = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, test_df["score"])
    hr5  = hit_rate_at_k(test_df, "score", k=5)
    hr10 = hit_rate_at_k(test_df, "score", k=10)
    ndcg5 = ndcg_at_k(test_df, "score", k=5)
    sr5  = sr_coverage_at_k(test_df, "score", k=5)
    sr_overall = test_df["real_sr_flag"].mean()  # baseline SR rate in pool

    metrics = {
        "test_auc":     round(float(auc), 4),
        "test_hr_5":    round(hr5, 4),
        "test_hr_10":   round(hr10, 4),
        "test_ndcg_5":  round(ndcg5, 4),
        "test_sr_cov_5": round(sr5, 4),
        "test_sr_baseline": round(float(sr_overall), 4),
        "train_rows":   len(train_df),
        "test_rows":    len(test_df),
        "test_bids":    int(test_df.groupby(["bid_ntce_no","bid_ntce_ord"]).ngroups),
        "test_winners": int(test_df["is_winner"].sum()),
        "scale_pos_weight": round(pos_w, 2),
    }

    print()
    print("=" * 70)
    print("BASELINE 평가 결과 (테스트 = 2025-01 ~ 2026-04)")
    print("=" * 70)
    print(f"  AUC                : {auc:.4f}")
    print(f"  HR@5  (히트율)     : {hr5:.4f}  ({hr5*100:.1f}% 공고에서 상위5개 안에 winner 있음)")
    print(f"  HR@10              : {hr10:.4f}")
    print(f"  NDCG@5             : {ndcg5:.4f}")
    print(f"  SR Coverage @5     : {sr5:.4f}  (vs pool baseline {sr_overall:.4f})")
    print(f"  test rows          : {len(test_df):,}")
    print(f"  test 공고 수       : {metrics['test_bids']}")
    print(f"  test winner 수     : {metrics['test_winners']}")
    print("=" * 70)

    # 피처 중요도
    fi = pd.DataFrame({
        "feature": X_train.columns,
        "importance": model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)
    print("\n[Top 15 feature importance]")
    print(fi.head(15).to_string(index=False))

    # 저장
    model.booster_.save_model(str(ARTIFACTS / "lgbm_baseline.txt"))
    with open(ARTIFACTS / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    fi.to_csv(ARTIFACTS / "feature_importance.csv", index=False)
    logger.info("saved → artifacts/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
