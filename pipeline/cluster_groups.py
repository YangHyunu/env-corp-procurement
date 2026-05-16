"""클러스터 그룹 5 enum + 한국어 라벨 → group 매핑 (한 곳에 집중).

pipeline.clustering._label_cluster 가 산출한 한국어 라벨을 분기 키로
직접 substring 매칭하던 코드를 group enum 으로 집중. ranker/recommend_v2
모두 이 enum 으로만 분기한다 (label 은 UI 표시 전용).
"""
from __future__ import annotations

from typing import Literal

ClusterGroup = Literal["veteran", "real_sr", "auto_sr", "dormant", "noise"]

VETERAN: ClusterGroup = "veteran"   # 환경공단 주력 공급사 (단골)
REAL_SR: ClusterGroup = "real_sr"   # 장애인·사회적기업 활성
AUTO_SR: ClusterGroup = "auto_sr"   # 여성 대표 자동등록 SR
DORMANT: ClusterGroup = "dormant"   # 활동중단 / 무낙찰
NOISE:   ClusterGroup = "noise"     # 분류외 outlier


def label_to_group(label: str | None) -> ClusterGroup | None:
    """한국어 cluster_label → group enum. 미인식이면 None.

    매칭 순서가 중요: '장애인·사회적기업' 가 '사회적기업' 보다 먼저.
    """
    if not label:
        return None
    if "환경공단 주력" in label:
        return VETERAN
    if "장애인·사회적기업" in label or "장애인" in label or "사회적기업" in label:
        return REAL_SR
    if "여성 대표 자동등록" in label or "자동등록 SR" in label:
        return AUTO_SR
    if "무낙찰" in label or "활동중단" in label:
        return DORMANT
    if "분류외" in label:
        return NOISE
    return None
