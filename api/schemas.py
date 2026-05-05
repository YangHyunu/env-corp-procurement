"""API request/response schemas (Pydantic)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from pipeline.policy import SR_LEGAL_FLOOR_FRACTION


class WeightVector(BaseModel):
    sr_diversity:          float = Field(ge=SR_LEGAL_FLOOR_FRACTION, le=1.0)  # 법정 하한
    track_record:          float = Field(ge=0.0, le=1.0)
    price_competitiveness: float = Field(ge=0.0, le=1.0)
    supply_stability:      float = Field(ge=0.0, le=1.0)

    @field_validator("supply_stability")
    @classmethod
    def _sum_one(cls, v, info):
        data = info.data
        s = (
            data.get("sr_diversity", 0)
            + data.get("track_record", 0)
            + data.get("price_competitiveness", 0)
            + v
        )
        if abs(s - 1.0) > 1e-3:
            raise ValueError(f"weights must sum to 1.0 (got {s:.4f})")
        return v


class SrFilterReq(BaseModel):
    require_any_sr: bool = False
    female_ceo: bool = False
    disabled_corp: bool = False
    social_corp: bool = False


class RecommendRequest(BaseModel):
    item_code: str = Field(min_length=10, max_length=10)
    weights: WeightVector | None = None
    sr_filter: SrFilterReq | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class ItemSummary(BaseModel):
    item_code: str
    item_name: str
    bid_count: int


class CompanyAward(BaseModel):
    bid_ntce_no: str
    bid_ntce_nm: str | None
    fnl_sucsf_date: str | None
    sucsfbid_amt: int | None
    sucsfbid_rate: float | None
    dminstt_nm: str | None
    item_code: str | None
    item_name: str | None


class CompanyDetail(BaseModel):
    brn: str
    corp_name: str
    corp_size: str | None
    region_code: str | None
    addr_sigungu: str | None
    is_manufacturer: bool
    sr_count: int
    sr_badges: list[str]
    g2b_registered_at: str | None
    awards: list[CompanyAward]
    award_total_count: int
    award_total_amt: int


class KpiResponse(BaseModel):
    item_code: str
    item_name: str | None
    matched_count: int           # mart_item_supply 풀 (item에 등록된 BRN 수)
    sr_coverage_pct: float       # 풀 내 SR 보유 비율
    cluster_count: int | None    # MVP 스텁 None
    recommend_threshold_pct: float  # composite ≥ 0.5인 BRN 비율


class RecommendationItem(BaseModel):
    rank: int
    brn: str
    corp_name: str
    composite_score: float
    axes: dict[str, float]
    weighted_segments: dict[str, float]
    sr_badges: list[str]
    award_summary: dict[str, Any]
    reason: str
    is_sr_demoted: bool


class RecommendResponse(BaseModel):
    item_code: str
    matched_count: int
    sr_coverage_pct: float
    recommendations: list[RecommendationItem]
    meta: dict[str, Any]


# ── v2: 사전탐색 모드 ──────────────────────────────────────────────
class SrFilterV2(BaseModel):
    female_ceo: bool = False
    disabled_corp: bool = False
    social_corp: bool = False


class RecommendV2Request(BaseModel):
    item_keyword: str = Field(min_length=1, max_length=50)
    budget_million_won: int = Field(ge=1, le=100_000)
    sr_filter: SrFilterV2 = Field(default_factory=SrFilterV2)
    top_k: int = Field(default=5, ge=1, le=20)


class ExpectedPrice(BaseModel):
    point: int                       # KRW
    point_million: int
    q25: int | None = None           # KRW
    q75: int | None = None
    q25_million: int | None = None
    q75_million: int | None = None
    sigma_pp: float | None = None
    market_diff_pp: float | None = None
    n_samples: int


class RiskInfo(BaseModel):
    grade: Literal["안전", "양호", "주의", "미확인"]
    top1_count: int
    lost_count: int
    lost_ratio: float
    recent_lost: int
    dormant_months: int | None = None
    is_dormant: bool = False


class SupplyStability(BaseModel):
    g2b_age_years: float | None = None
    award_total_amt: int
    is_manufacturer: bool
    last_award_at: str | None = None


class AwardItemV2(BaseModel):
    bid_ntce_no: str
    bid_ntce_nm: str | None = None
    fnl_sucsf_date: str | None = None
    sucsfbid_amt: int | None = None
    sucsfbid_rate: float | None = None


class PrecedentItem(BaseModel):
    bid_ntce_no: str
    bid_ntce_nm: str | None = None
    fnl_sucsf_date: str | None = None
    sucsfbid_amt: int | None = None
    bidwinnr_brn: str | None = None
    winner_corp_name: str | None = None


class ChartsData(BaseModel):
    bid_rate_distribution: list[float]
    bid_amt_distribution: list[int]


class SummaryStatsV2(BaseModel):
    award_count: int
    avg_bid_rate: float | None = None
    last_award_at: str | None = None
    lost_count: int


class MarketDepth(BaseModel):
    registered: int
    env_active: int


class KpiV2(BaseModel):
    pool_size: int
    market_depth: MarketDepth
    sr_count: int
    sr_pct: float
    avg_expected_price_million: int | None = None
    supply_risk: str                 # 낮음/보통/높음
    contract_recommend: str          # 수의계약/제한경쟁/일반경쟁


class ComplianceInfo(BaseModel):
    sr_in_top_k: int
    sr_pct_top_k: float
    obligation_threshold_pct: float
    obligation_met: bool


class RecommendationV2Item(BaseModel):
    rank: int
    brn: str
    corp_name: str | None = None
    tier: str                        # A 강추 / B 추천 / C 검토
    badges: list[str]
    summary_stats: SummaryStatsV2
    expected_price: ExpectedPrice
    risk: RiskInfo
    supply_stability: SupplyStability
    recent_awards: list[AwardItemV2]
    precedents: list[PrecedentItem]
    charts: ChartsData
    rule_score: float
    ml_score: float | None = None    # (B) LGBM 도입 시 채워짐
    score_used: str = "rule"
    reason: str


class RecommendV2Response(BaseModel):
    item_keyword: str
    matched_prefix4: list[str]
    cutoff_date: str
    kpi: KpiV2 | None = None
    compliance: ComplianceInfo | None = None
    recommendations: list[RecommendationV2Item]
    meta: dict[str, Any]


class MetaResponse(BaseModel):
    data_cutoff: str
    freshness_days: int
    stale_warning: bool
    sources: dict[str, str]
