"""
BRN 단위 다차원 벡터 클러스터링 — 공모전 PDF 핵심 요건 구현.

설계 (CLAUDE.md §13 AI 클러스터링 원안 반영):
  1. 학습 데이터: warm BRN (env_corp/env_domain 누적 거래 1+ 활성 업체).
     ~1,300~1,400 BRN 규모 → 5~10개 군집 도출 적정.
  2. 피처 (15차원):
        A. 공급역량  (5): env_award_count_total, env_award_amt_total_log,
                          env_avg_rate, env_dminstt_count, g2b_age_years
        B. 도메인   (3): prefix4_diversity, main_prdct_consistency, is_manufacturer
        C. SR       (3): sr_count, real_sr_flag, female_ceo_flag
        D. 리스크   (2): bid_lost_ratio, dormant_months
        E. 가격     (2): avg_unit_price_zscore, price_volatility
  3. 표준화: RobustScaler (이상치 강건 — 환경공단 거대 BRN 영향 완화).
  4. 차원축소: UMAP 5D (학습용) + UMAP 2D (시각화). 두 모델 분리 학습.
        random_state=42 고정 (재현성).
  5. 클러스터링: HDBSCAN(min_cluster_size=30) 메인 + KMeans(k=8) baseline.
  6. 라벨링: 자동 휴리스틱 — "환경공단 베테랑 SR" / "신생 SR 기업" 등.
  7. 신뢰 군집(is_sr_trusted): sr_pct ≥ 50% AND avg_env_award_count ≥ 1.

CLAUDE.md §9 준수:
  - 새 라이브러리 X (umap-learn/hdbscan/scikit-learn은 [ml] extra에 이미 정의)
  - calibration 안 된 cluster_prob raw 노출 X — 등급(상/중/하)으로만 표출
  - cold-start: 학습 미포함 BRN은 cluster_id=-2 (recommend 단계 fallback)
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from pipeline.cluster_groups import label_to_group

logger = logging.getLogger(__name__)


# ── 도메인 매핑 (운영팀이 보는 라벨/해설용) ─────────────────────────
# prefix4 → 한글 품목 카테고리 (DB mode 산출 기반, 12 군집 dominant 커버)
PREFIX4_LABEL: dict[str, str] = {
    "1214": "산업용 가스 (산소·질소·헬륨)",
    "1216": "실험·분석 시약 (살균제·시약키트)",
    "2410": "운반·물류 장비 (지게차·엘리베이터)",
    "3010": "건자재 (골재·목재)",
    "3912": "전기 설비 (배전반·계장제어·UPS)",
    "4015": "펌프·압축기 (수중펌프·공기압축기)",
    "4111": "계측 장비 (계측기·수질분석기·유량계)",
    "4710": "수처리 약품 (응집제·여과재)",
}

# region_code → 한글 지역명 (행안부 시도코드)
REGION_LABEL: dict[str, str] = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천",
    "29": "광주", "30": "대전", "31": "울산", "36": "세종",
    "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남",
    "50": "제주",
}


def label_prefix4(code: Optional[str]) -> str:
    """prefix4 코드 → 한글 카테고리. 미매핑은 코드 그대로."""
    if not code:
        return "품목 미상"
    return PREFIX4_LABEL.get(str(code), f"품목코드 {code}")


def label_region(code: Optional[str]) -> str:
    """region 코드 → 한글 시도명. 미매핑은 코드 그대로."""
    if not code:
        return "지역 미상"
    return REGION_LABEL.get(str(code), f"지역코드 {code}")


# ── 피처 정의 ─────────────────────────────────────────────────────
# (학습 입력 컬럼 순서 — RobustScaler/UMAP/HDBSCAN 모두 이 순서를 따름)
FEATURE_COLUMNS: list[str] = [
    # A. 공급역량
    "env_award_count_total",
    "env_award_amt_total_log",     # log1p(amt) — 단위가 큰 변수 정규화
    "env_avg_rate",                # 결측 시 0
    "env_dminstt_count",
    "g2b_age_years",
    # B. 도메인 다변화
    "prefix4_diversity",
    "main_prdct_consistency",      # 0 or 1 (BRN 대표품명이 실 낙찰 prefix4에 포함되는지)
    "is_manufacturer_flag",        # 0/1
    # C. SR
    "sr_count",                    # 0~3
    "real_sr_flag",                # 0/1 (장애인 OR 사회적)
    "female_ceo_flag",             # 0/1
    # D. 리스크
    "bid_lost_ratio",              # 0~1
    "dormant_months",              # 0~999, 활동중단 시그널
    # E. 가격
    "avg_unit_price_zscore",       # prefix4 내 단가 z-score (≈ -3~3)
    "price_volatility",            # 낙찰률 표준편차
]
N_FEATURES: int = len(FEATURE_COLUMNS)


# ── 학습 하이퍼파라미터 ───────────────────────────────────────────
@dataclass(frozen=True)
class ClusteringConfig:
    """학습 설정 (재현성을 위해 frozen + 기본값 명시)."""
    umap_n_components_train: int = 5      # 학습 차원 (HDBSCAN 입력)
    umap_n_components_viz:   int = 2      # 시각화 차원 (대시보드 산점도)
    umap_n_neighbors:        int = 15
    umap_min_dist:           float = 0.1
    umap_metric:             str = "euclidean"
    hdbscan_min_cluster_size: int = 30    # 1,300 BRN ÷ 30 ≈ 최대 ~40 군집 가능, 실제 5~10
    hdbscan_min_samples:      int = 10
    hdbscan_metric:           str = "euclidean"
    kmeans_k:                int = 8      # baseline 비교용
    random_state:            int = 42

    # 신뢰 군집 임계값
    sr_trusted_pct:          float = 50.0      # sr_pct ≥ 50%
    sr_trusted_min_avg_env:  float = 1.0       # avg_env_award_count ≥ 1.0

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# ── 학습 결과 컨테이너 ────────────────────────────────────────────
@dataclass
class ClusteringArtifact:
    """학습 산출물 — pickle 직렬화 가능."""
    config: ClusteringConfig
    feature_columns: list[str]
    scaler: Any                    # sklearn RobustScaler (fitted)
    umap_train: Any                # umap.UMAP (5D, fitted)
    umap_viz:   Any                # umap.UMAP (2D, fitted)
    hdbscan:    Any                # hdbscan.HDBSCAN (fitted)
    kmeans:     Any                # sklearn KMeans (fitted, baseline)
    feature_medians: dict[str, float]   # 결측 보정용 (운영 BRN 추론 시)
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("clustering artifact saved → %s", path)

    @classmethod
    def load(cls, path: Path) -> "ClusteringArtifact":
        with open(path, "rb") as f:
            return pickle.load(f)


# ── 피처 전처리 (DB 결과 → 학습 행렬) ─────────────────────────────
def prepare_feature_matrix(
    df: pd.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
    medians: Optional[dict[str, float]] = None,
) -> tuple[np.ndarray, dict[str, float]]:
    """원본 DataFrame → 학습 가능한 (n, d) numpy 행렬.

    - 결측 (NaN/None): median 으로 채움. medians 인자 없으면 학습 데이터의
      median 으로 산출하고 반환 (운영 추론 시 학습 medians 재사용).
    - amt 컬럼은 log1p 변환 (큰 단위 정규화).
    """
    df = df.copy()
    df["env_award_amt_total_log"] = np.log1p(df["env_award_amt_total"].fillna(0).astype(float))

    if medians is None:
        medians = {}
        for col in feature_columns:
            if col not in df.columns:
                logger.warning("feature %s missing — defaulting to 0", col)
                df[col] = 0.0
            medians[col] = float(df[col].median(skipna=True))

    for col in feature_columns:
        if col not in df.columns:
            df[col] = medians.get(col, 0.0)
        df[col] = df[col].fillna(medians[col]).astype(float)

    matrix = df[feature_columns].to_numpy()
    return matrix, medians


# ── 학습 ──────────────────────────────────────────────────────────
def fit(
    df: pd.DataFrame,
    config: ClusteringConfig = ClusteringConfig(),
) -> tuple[ClusteringArtifact, pd.DataFrame]:
    """학습 메인.

    Returns
    -------
    artifact : ClusteringArtifact
        scaler/umap/hdbscan 묶음 (pickle 가능)
    assignments : pd.DataFrame
        columns: brn, cluster_id, cluster_prob, kmeans_id, umap_x, umap_y
    """
    # late import (uv sync --extra ml 미설치 환경에서도 모듈 import 가능하게)
    import hdbscan
    import umap
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import RobustScaler

    if "brn" not in df.columns:
        raise ValueError("input df must have 'brn' column")
    if len(df) < config.hdbscan_min_cluster_size * 2:
        raise ValueError(
            f"too few BRNs ({len(df)}) for clustering — "
            f"need at least {config.hdbscan_min_cluster_size * 2}"
        )

    logger.info("preparing feature matrix: %d BRNs × %d features", len(df), N_FEATURES)
    X, medians = prepare_feature_matrix(df)

    # 1) 표준화
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    # 2) UMAP 5D (학습용)
    logger.info("UMAP 5D fitting (n_neighbors=%d)...", config.umap_n_neighbors)
    umap_train = umap.UMAP(
        n_components=config.umap_n_components_train,
        n_neighbors=config.umap_n_neighbors,
        min_dist=config.umap_min_dist,
        metric=config.umap_metric,
        random_state=config.random_state,
    )
    X_emb_train = umap_train.fit_transform(X_scaled)

    # 3) UMAP 2D (시각화) — 학습 모델과 분리하여 안정적 산점도
    logger.info("UMAP 2D fitting (visualization)...")
    umap_viz = umap.UMAP(
        n_components=config.umap_n_components_viz,
        n_neighbors=config.umap_n_neighbors,
        min_dist=config.umap_min_dist,
        metric=config.umap_metric,
        random_state=config.random_state,
    )
    X_emb_viz = umap_viz.fit_transform(X_scaled)

    # 4) HDBSCAN
    logger.info("HDBSCAN fitting (min_cluster_size=%d)...", config.hdbscan_min_cluster_size)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=config.hdbscan_min_cluster_size,
        min_samples=config.hdbscan_min_samples,
        metric=config.hdbscan_metric,
        prediction_data=True,           # 신규 BRN approximate_predict 가능
    )
    cluster_labels = clusterer.fit_predict(X_emb_train)
    cluster_probs = clusterer.probabilities_

    n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    n_noise = int((cluster_labels == -1).sum())
    logger.info(
        "HDBSCAN: %d clusters, %d noise points (%.1f%%)",
        n_clusters, n_noise, 100.0 * n_noise / len(cluster_labels),
    )

    # 5) KMeans baseline
    logger.info("KMeans baseline (k=%d)...", config.kmeans_k)
    kmeans = KMeans(
        n_clusters=config.kmeans_k,
        random_state=config.random_state,
        n_init=10,
    )
    kmeans_labels = kmeans.fit_predict(X_emb_train)

    artifact = ClusteringArtifact(
        config=config,
        feature_columns=FEATURE_COLUMNS,
        scaler=scaler,
        umap_train=umap_train,
        umap_viz=umap_viz,
        hdbscan=clusterer,
        kmeans=kmeans,
        feature_medians=medians,
    )

    assignments = pd.DataFrame({
        "brn":           df["brn"].values,
        "cluster_id":    cluster_labels.astype(int),
        "cluster_prob":  cluster_probs.astype(float),
        "kmeans_id":     kmeans_labels.astype(int),
        "umap_x":        X_emb_viz[:, 0].astype(float),
        "umap_y":        X_emb_viz[:, 1].astype(float),
    })

    return artifact, assignments


# ── 군집 프로파일 산출 ─────────────────────────────────────────────
@dataclass
class ClusterProfile:
    """군집 1개의 통계 + 라벨."""
    cluster_id: int
    label: str
    brn_count: int
    avg_env_award_count: float
    avg_env_award_amt:   int
    avg_env_avg_rate:    Optional[float]
    avg_g2b_age_years:   Optional[float]
    avg_prefix4_diversity: float
    avg_sr_count:        float
    avg_bid_lost_ratio:  float
    avg_dormant_months:  float
    sr_brn_count:        int
    real_sr_brn_count:   int
    manufacturer_count:  int
    sr_pct:              float
    is_sr_trusted:       bool
    representative_brns: list[str]
    representative_prefix4: Optional[str]
    representative_region:  Optional[str]
    item_label:    Optional[str] = None    # PREFIX4_LABEL 변환값
    region_label:  Optional[str] = None    # REGION_LABEL 변환값
    narrative:     Optional[str] = None    # 평어체 1줄 해설 (보고서 카드용)
    group:         Optional[str] = None    # cluster_groups enum (label_to_group 산출)


def _label_cluster(stats: dict[str, Any]) -> str:
    """자동 라벨 휴리스틱 — 운영팀(공무원) 가독성 우선.

    "베테랑/prefix4 4710" 같은 추상·코드 표현 X.
    "환경공단 수처리 약품 주력 공급사 (경기, 평균 13억)" 형태로 한국어 도메인 용어 사용.
    """
    cid = stats["cluster_id"]
    if cid == -1:
        return "분류외 (어느 군집에도 안 묶임)"

    sr_pct = stats["sr_pct"]
    real_sr_pct = stats.get("real_sr_pct", 0.0)
    avg_env = stats["avg_env_award_count"]
    avg_age = stats.get("avg_g2b_age_years") or 0
    avg_lost = stats["avg_bid_lost_ratio"]
    avg_dormant = stats["avg_dormant_months"]
    mfr_pct = stats.get("manufacturer_pct", 0.0)
    avg_amt = stats.get("avg_env_award_amt", 0)

    item = label_prefix4(stats.get("dominant_prefix4"))
    mfr = "제조사" if mfr_pct >= 70 else ("유통·서비스사" if mfr_pct <= 30 else "제조·유통 혼재")
    amt_eok = avg_amt / 1e8  # 억 원

    # 우선순위: 진짜 SR → 자동판별 SR → 환경공단 주력 → 활동저조 → 고탈락 → 기타
    # ※ 본거지(지역)는 군집 라벨에 안 넣음 — 라벨은 군집 도메인 특성만, 지역은 BRN 메타로 분리.
    if real_sr_pct >= 50:
        return f"장애인·사회적기업 100% — {item} {mfr}"
    if sr_pct >= 50 and real_sr_pct < 50:
        return (
            f"여성 대표 자동등록 SR (실제 인증 {real_sr_pct:.0f}%만 보유) — "
            f"{item} 등록사"
        )
    if avg_env >= 3.0 and avg_lost < 0.2:
        return (
            f"환경공단 주력 공급사 — {item} {mfr} "
            f"(한 곳당 평균 {amt_eok:.1f}억 누적)"
        )
    if avg_dormant >= 24:
        return (
            f"최근 {avg_dormant:.0f}개월 무낙찰 — {item} {mfr} "
            f"(등록 {avg_age:.0f}년차)"
        )
    if avg_lost >= 0.3:
        return f"1순위였다가 탈락 {avg_lost*100:.0f}% — {item}"
    if avg_age >= 10:
        return f"오래 등록된 소규모 공급사 — {item} {mfr} (등록 {avg_age:.0f}년차)"
    return f"기타 — {item} {mfr}"


def _narrative_for(p: "ClusterProfile") -> str:
    """군집 1개에 대한 1줄 평어체 해설 — 운영팀(공무원) 보고서 카드용.

    숫자 가공: 거래액 → 억, 비율 → %, dormant → 개월.
    """
    n = p.brn_count
    item = p.item_label or "품목 미상"
    mfr = (
        "제조사" if p.manufacturer_count >= 0.7 * n else
        ("유통·서비스사" if p.manufacturer_count <= 0.3 * n else "제조·유통 혼재")
    )
    amt_eok = p.avg_env_award_amt / 1e8
    real_sr_pct = 100.0 * p.real_sr_brn_count / n if n else 0.0

    if p.cluster_id == -1:
        return (
            f"어느 군집에도 잘 묶이지 않은 outlier {n}곳입니다. 활동·도메인이 너무 "
            "특이해서 자동 분류가 안 된 BRN들이며, 추천 시 개별 검토가 필요합니다."
        )
    if real_sr_pct >= 50:
        return (
            f"{item}을(를) 공급하는 장애인·사회적기업 {n}곳입니다. "
            f"사회적가치법 우선구매 의무비율을 채울 때 가장 안전한 풀이며, "
            f"한 곳당 평균 환경공단 낙찰 {p.avg_env_award_count:.1f}건."
        )
    if p.sr_pct >= 50:
        return (
            f"여성 대표가 등록된 {item} 공급사 {n}곳입니다. 다만 조달업체 CSV "
            f"자동판별이라 실제 장애인·사회적기업 인증을 보유한 곳은 "
            f"{p.real_sr_brn_count}곳({real_sr_pct:.0f}%)에 불과하므로, 발주 전 "
            f"인증서 유효성 확인이 필요합니다."
        )
    if p.avg_env_award_count >= 3.0 and p.avg_bid_lost_ratio < 0.2:
        return (
            f"환경공단 본부·권역에 {item}을(를) 꾸준히 공급해 온 {mfr} {n}곳입니다. "
            f"한 곳당 누적 거래액 평균 {amt_eok:.1f}억 원, 평균 "
            f"{p.avg_env_award_count:.1f}건 낙찰. 이 도메인의 실질 발주 후보 풀입니다."
        )
    if p.avg_dormant_months >= 24:
        return (
            f"마지막 환경공단 낙찰이 평균 {p.avg_dormant_months:.0f}개월 전인 "
            f"{item} {mfr} {n}곳입니다. 등록 {p.avg_g2b_age_years or 0:.0f}년차로 "
            f"한때 활동했으나 최근 모습이 안 보입니다. 추천 시 활동 재개 여부 "
            f"확인이 필요합니다."
        )
    if p.avg_bid_lost_ratio >= 0.3:
        return (
            f"1순위였다가 최종 낙찰을 못 받은 비율이 평균 "
            f"{p.avg_bid_lost_ratio*100:.0f}%인 {item} 공급사 {n}곳입니다. "
            f"가격·서류 문제 가능성이 있어 추천 시 주의가 필요합니다."
        )
    if (p.avg_g2b_age_years or 0) >= 10:
        return (
            f"등록한 지 {p.avg_g2b_age_years or 0:.0f}년 된 소규모 {item} {mfr} "
            f"{n}곳입니다. 활동은 적지만 오래 살아남은 풀입니다."
        )
    return f"기타 분류 — {item} {mfr} {n}곳."


def compute_profiles(
    df: pd.DataFrame,
    assignments: pd.DataFrame,
    config: ClusteringConfig = ClusteringConfig(),
) -> list[ClusterProfile]:
    """클러스터별 평균 통계 + 라벨 산출.

    df: 학습 입력 DataFrame (brn + 모든 feature_columns + corp 메타)
    assignments: fit 의 두 번째 반환값 (brn, cluster_id, ...)
    """
    merged = df.merge(assignments[["brn", "cluster_id"]], on="brn", how="inner")
    profiles: list[ClusterProfile] = []

    for cid, grp in merged.groupby("cluster_id"):
        n = len(grp)
        sr_brn_count = int((grp["sr_count"] > 0).sum())
        real_sr_brn_count = int((grp["real_sr_flag"] > 0).sum())
        sr_pct = 100.0 * sr_brn_count / n if n else 0.0
        avg_env = float(grp["env_award_count_total"].mean())

        is_trusted = (
            cid != -1
            and sr_pct >= config.sr_trusted_pct
            and avg_env >= config.sr_trusted_min_avg_env
        )

        # 대표 BRN: env_award_count 상위 5개
        rep_brns = (
            grp.sort_values("env_award_count_total", ascending=False)
               .head(5)["brn"].astype(str).tolist()
        )

        # 대표 prefix4 / 권역 (mode)
        def _mode(s: pd.Series) -> Optional[str]:
            if s.isna().all():
                return None
            m = s.mode()
            return str(m.iloc[0]) if len(m) > 0 else None

        rep_prefix4 = _mode(grp.get("dominant_prefix4", pd.Series([], dtype=object)))
        rep_region = _mode(grp.get("region_code", pd.Series([], dtype=object)))

        avg_rate = grp["env_avg_rate"].replace(0, np.nan).mean(skipna=True)
        avg_age = grp["g2b_age_years"].replace(0, np.nan).mean(skipna=True)

        real_sr_pct = 100.0 * real_sr_brn_count / n if n else 0.0
        mfr_pct = 100.0 * int((grp["is_manufacturer_flag"] > 0).sum()) / n if n else 0.0

        stats: dict[str, Any] = {
            "cluster_id": int(cid),
            "brn_count":  n,
            "sr_pct":     sr_pct,
            "real_sr_pct": real_sr_pct,
            "manufacturer_pct": mfr_pct,
            "dominant_prefix4": rep_prefix4,
            "region_code":      rep_region,
            "avg_env_award_amt":     int(grp["env_award_amt_total"].mean()),
            "avg_env_award_count":   avg_env,
            "avg_g2b_age_years":     None if np.isnan(avg_age) else float(avg_age),
            "avg_bid_lost_ratio":    float(grp["bid_lost_ratio"].mean()),
            "avg_dormant_months":    float(grp["dormant_months"].mean()),
            "avg_prefix4_diversity": float(grp["prefix4_diversity"].mean()),
        }

        profile = ClusterProfile(
            cluster_id=int(cid),
            label=_label_cluster(stats),
            brn_count=n,
            avg_env_award_count=avg_env,
            avg_env_award_amt=int(grp["env_award_amt_total"].mean()),
            avg_env_avg_rate=None if np.isnan(avg_rate) else float(avg_rate),
            avg_g2b_age_years=stats["avg_g2b_age_years"],
            avg_prefix4_diversity=stats["avg_prefix4_diversity"],
            avg_sr_count=float(grp["sr_count"].mean()),
            avg_bid_lost_ratio=stats["avg_bid_lost_ratio"],
            avg_dormant_months=stats["avg_dormant_months"],
            sr_brn_count=sr_brn_count,
            real_sr_brn_count=real_sr_brn_count,
            manufacturer_count=int((grp["is_manufacturer_flag"] > 0).sum()),
            sr_pct=sr_pct,
            is_sr_trusted=is_trusted,
            representative_brns=rep_brns,
            representative_prefix4=rep_prefix4,
            representative_region=rep_region,
            item_label=label_prefix4(rep_prefix4),
            region_label=label_region(rep_region),
        )
        profile.narrative = _narrative_for(profile)
        profile.group = label_to_group(profile.label)
        profiles.append(profile)

    return sorted(profiles, key=lambda p: p.cluster_id)


# ── 품질 메트릭 ───────────────────────────────────────────────────
def compute_metrics(
    artifact: ClusteringArtifact,
    df: pd.DataFrame,
    assignments: pd.DataFrame,
) -> dict[str, Any]:
    """silhouette / DBI 산출."""
    from sklearn.metrics import davies_bouldin_score, silhouette_score

    X, _ = prepare_feature_matrix(
        df, feature_columns=artifact.feature_columns,
        medians=artifact.feature_medians,
    )
    X_scaled = artifact.scaler.transform(X)
    X_emb = artifact.umap_train.transform(X_scaled)

    labels = assignments["cluster_id"].to_numpy()
    mask = labels != -1   # 노이즈 제외
    n_real_clusters = len(set(labels[mask]))

    if n_real_clusters >= 2 and mask.sum() >= 2:
        sil = float(silhouette_score(X_emb[mask], labels[mask]))
        dbi = float(davies_bouldin_score(X_emb[mask], labels[mask]))
    else:
        sil, dbi = None, None

    return {
        "n_brns":       int(len(df)),
        "n_features":   N_FEATURES,
        "n_clusters":   n_real_clusters,
        "n_noise":      int((labels == -1).sum()),
        "silhouette_score": sil,
        "davies_bouldin_score": dbi,
        "feature_list": artifact.feature_columns,
        "hyperparams":  artifact.config.to_dict(),
    }


# ── 운영 추론 (신규 BRN — recommend 시점 cold-start) ────────────────
def predict_one(
    artifact: ClusteringArtifact,
    feature_row: dict[str, float],
) -> tuple[int, float, float, float]:
    """단일 BRN → (cluster_id, cluster_prob, umap_x, umap_y).

    학습 시점에 없던 BRN을 recommend 단계에서 분류.
    HDBSCAN.approximate_predict 활용.
    """
    import hdbscan as hdbscan_mod

    # 1) feature row → 행렬 1행
    df = pd.DataFrame([feature_row])
    X, _ = prepare_feature_matrix(
        df,
        feature_columns=artifact.feature_columns,
        medians=artifact.feature_medians,
    )
    X_scaled = artifact.scaler.transform(X)

    # 2) UMAP transform (학습 시 fit된 모델로)
    X_emb_train = artifact.umap_train.transform(X_scaled)
    X_emb_viz = artifact.umap_viz.transform(X_scaled)

    # 3) HDBSCAN approximate_predict
    labels, probs = hdbscan_mod.approximate_predict(artifact.hdbscan, X_emb_train)
    return int(labels[0]), float(probs[0]), float(X_emb_viz[0, 0]), float(X_emb_viz[0, 1])


# ── 키워드 ↔ 군집 매칭 (recommend 단계 cluster_fit 산출용) ──────────
def cluster_fit_score(
    bnr_cluster_id: int,
    bnr_cluster_prob: float,
    keyword_dominant_clusters: list[int],
    trusted_clusters: set[int],
) -> float:
    """BRN의 키워드별 적합도 [0, 1].

    keyword_dominant_clusters: 사용자가 입력한 키워드(품목)에서 과거 활약한
                               상위 클러스터 ID 리스트 (recommend 단계에서 산출)
    trusted_clusters:          is_sr_trusted=True 인 클러스터 ID 집합

    규칙:
      - 키워드 dominant 1순위 군집 = 1.0
      - 키워드 dominant 2~3순위 군집 = 0.7
      - 신뢰 군집(is_sr_trusted) = 0.6
      - 그 외 일반 군집 = 0.4
      - 노이즈(-1) / 미분류(-2) = 0.3 (불확실성 페널티)

    cluster_prob 으로 추가 가중 (membership 약하면 점수 약화).
    """
    if bnr_cluster_id < 0:
        # 노이즈/미분류 — 약한 fallback
        return 0.3

    if keyword_dominant_clusters and bnr_cluster_id == keyword_dominant_clusters[0]:
        base = 1.0
    elif bnr_cluster_id in keyword_dominant_clusters[:3]:
        base = 0.7
    elif bnr_cluster_id in trusted_clusters:
        base = 0.6
    else:
        base = 0.4

    # membership strength 가중 (확률 0.5 이하면 약화)
    confidence = max(0.5, min(1.0, bnr_cluster_prob + 0.5))
    return float(base * confidence)
