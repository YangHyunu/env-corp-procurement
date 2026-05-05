"""
LightGBM Ranker 학습 + 평가.

Classifier 대신 학습 목표 자체를 순위(rank)로 정의:
  - 각 공고 = 한 그룹
  - 그룹 안에서 BRN 점수를 매겨 winner를 상위로 올리도록 학습
  - objective='lambdarank', eval='ndcg@5'

장점:
  - Class imbalance 자체가 문제가 안 됨 (그룹 내 상대 순위 학습)
  - NDCG를 직접 최적화

사용:
  uv run python scripts/train_ranker.py
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
from dotenv import find_dotenv, load_dotenv
from sklearn.metrics import roc_auc_score

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_ranker")

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"

CATEGORICAL = [
    "corp_size", "region_code", "cntrct_cncls_mthd_nm",
    "bid_dminstt_cd", "bid_dtil_prdct_no",
]

DROP_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "brn",
    "is_winner", "cutoff_date", "last_synced_at",
    "participated_in_bid",
]

BOOL_COLS = [
    "is_manufacturer", "female_ceo_flag", "disabled_corp_flag",
    "social_corp_flag", "real_sr_flag", "main_prdct_match",
]


def load_data() -> pd.DataFrame:
    with psycopg2.connect(DSN) as conn:
        df = pd.read_sql("SELECT * FROM mart_features_at_bid", conn)
    for c in BOOL_COLS + ["is_winner", "participated_in_bid"]:
        if c in df.columns:
            df[c] = df[c].map({True: 1, False: 0}).fillna(0).astype("int8")
    logger.info("loaded %s rows × %s cols", f"{len(df):,}", df.shape[1])
    return df


def split(df: pd.DataFrame):
    train = df[df["cutoff_date"].astype(str) <= TRAIN_END].copy()
    test = df[df["cutoff_date"].astype(str) >= TEST_START].copy()
    # group 단위로 정렬해야 LGBMRanker가 group 인식
    train = train.sort_values(["bid_ntce_no", "bid_ntce_ord"]).reset_index(drop=True)
    test  = test.sort_values(["bid_ntce_no", "bid_ntce_ord"]).reset_index(drop=True)
    logger.info("train=%s rows (pos %.2f%%), test=%s rows (pos %.2f%%)",
                f"{len(train):,}", 100*train["is_winner"].mean(),
                f"{len(test):,}", 100*test["is_winner"].mean())
    return train, test


def prep(df: pd.DataFrame):
    y = df["is_winner"].astype(int).values
    # group 크기 (각 공고당 후보 수)
    groups = df.groupby(["bid_ntce_no", "bid_ntce_ord"], sort=False).size().values
    X = df.drop(columns=DROP_COLS)
    for c in CATEGORICAL:
        if c in X.columns:
            X[c] = X[c].astype("category")
    return X, y, groups


# ── 평가 메트릭 ──────────────────────────────────────────
def hit_rate_at_k(df, score_col, k=5):
    hits = total = 0
    for _, g in df.groupby(["bid_ntce_no", "bid_ntce_ord"]):
        if (g["is_winner"] == 1).sum() == 0:
            continue
        topk = g.nlargest(k, score_col)
        if (topk["is_winner"] == 1).sum() > 0:
            hits += 1
        total += 1
    return hits / max(total, 1)


def ndcg_at_k(df, score_col, k=5):
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


def sr_coverage_at_k(df, score_col, k=5):
    rates = []
    for _, g in df.groupby(["bid_ntce_no", "bid_ntce_ord"]):
        topk = g.nlargest(k, score_col)
        if len(topk) == 0:
            continue
        rates.append(topk["real_sr_flag"].mean())
    return float(np.mean(rates)) if rates else 0.0


# ── main ─────────────────────────────────────────────────
def main() -> int:
    df = load_data()
    train_df, test_df = split(df)

    X_train, y_train, g_train = prep(train_df)
    X_test,  y_test,  g_test  = prep(test_df)

    cat_features = [c for c in CATEGORICAL if c in X_train.columns]

    model = lgb.LGBMRanker(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=-1,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=0.1,
        objective="lambdarank",
        metric="ndcg",
        eval_at=[1, 3, 5, 10],
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    logger.info("training Ranker (lambdarank, NDCG@5)...")
    model.fit(
        X_train, y_train,
        group=g_train,
        eval_set=[(X_test, y_test)],
        eval_group=[g_test],
        eval_at=[1, 3, 5, 10],
        categorical_feature=cat_features,
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
    )

    test_df = test_df.copy()
    test_df["score"] = model.predict(X_test)

    auc = roc_auc_score(y_test, test_df["score"])
    hr5 = hit_rate_at_k(test_df, "score", 5)
    hr10 = hit_rate_at_k(test_df, "score", 10)
    ndcg5 = ndcg_at_k(test_df, "score", 5)
    sr5 = sr_coverage_at_k(test_df, "score", 5)
    sr_overall = test_df["real_sr_flag"].mean()

    metrics = {
        "model": "LGBMRanker (lambdarank)",
        "test_auc": round(float(auc), 4),
        "test_hr_5": round(hr5, 4),
        "test_hr_10": round(hr10, 4),
        "test_ndcg_5": round(ndcg5, 4),
        "test_sr_cov_5": round(sr5, 4),
        "test_sr_baseline": round(float(sr_overall), 4),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "test_bids": int(test_df.groupby(["bid_ntce_no","bid_ntce_ord"]).ngroups),
        "test_winners": int(test_df["is_winner"].sum()),
    }

    print()
    print("=" * 70)
    print("RANKER 평가 결과 (테스트 = 2025-01 ~ 2026-04)")
    print("=" * 70)
    print(f"  AUC                : {auc:.4f}")
    print(f"  HR@5  (히트율)     : {hr5:.4f}  ({hr5*100:.1f}% 공고에서 상위5개 안에 winner)")
    print(f"  HR@10              : {hr10:.4f}")
    print(f"  NDCG@5             : {ndcg5:.4f}")
    print(f"  SR Coverage @5     : {sr5:.4f}  (vs pool baseline {sr_overall:.4f})")
    print("=" * 70)

    print("\n[Top 15 feature importance — gain]")
    fi = pd.DataFrame({
        "feature": X_train.columns,
        "importance": model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)
    print(fi.head(15).to_string(index=False))

    model.booster_.save_model(str(ARTIFACTS / "lgbm_ranker.txt"))
    with open(ARTIFACTS / "metrics_ranker.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    fi.to_csv(ARTIFACTS / "feature_importance_ranker.csv", index=False)
    logger.info("saved → artifacts/")

    # baseline classifier 메트릭과 비교 출력
    base_path = ARTIFACTS / "metrics.json"
    if base_path.exists():
        with open(base_path) as f:
            base = json.load(f)
        print("\n[Baseline Classifier vs Ranker 비교]")
        print(f"  {'':<18} {'Classifier':>12} {'Ranker':>12} {'Δ':>10}")
        for k in ["test_auc", "test_hr_5", "test_hr_10", "test_ndcg_5", "test_sr_cov_5"]:
            b = base.get(k, 0)
            r = metrics[k]
            d = r - b
            arrow = "↑" if d > 0 else ("↓" if d < 0 else "·")
            print(f"  {k:<18} {b:>12.4f} {r:>12.4f}   {arrow}{abs(d):>7.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
