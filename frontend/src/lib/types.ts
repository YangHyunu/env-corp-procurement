// ── V2 타입 (api/schemas.py 1:1 미러) ──────────────────────────────

export interface SrFilterV2 {
  female_ceo: boolean
  disabled_corp: boolean
  social_corp: boolean
}

export interface RecommendV2Request {
  item_keyword: string
  budget_million_won: number
  sr_filter: SrFilterV2
  top_k: number
}

export interface ExpectedPrice {
  point: number
  point_million: number
  q25: number | null
  q75: number | null
  q25_million: number | null
  q75_million: number | null
  sigma_pp: number | null
  market_diff_pp: number | null
  n_samples: number
}

export interface RiskInfo {
  grade: '안전' | '양호' | '주의' | '미확인'
  top1_count: number
  lost_count: number
  lost_ratio: number
  recent_lost: number
  dormant_months: number | null
  is_dormant: boolean
}

export interface SupplyStability {
  g2b_age_years: number | null
  award_total_amt: number
  is_manufacturer: boolean
  last_award_at: string | null
}

export interface AwardItemV2 {
  bid_ntce_no: string
  bid_ntce_nm: string | null
  fnl_sucsf_date: string | null
  sucsfbid_amt: number | null
  sucsfbid_rate: number | null
}

export interface PrecedentItem {
  bid_ntce_no: string
  bid_ntce_nm: string | null
  fnl_sucsf_date: string | null
  sucsfbid_amt: number | null
  bidwinnr_brn: string | null
  winner_corp_name: string | null
}

export interface ChartsData {
  bid_rate_distribution: number[]
  bid_amt_distribution: number[]
}

export interface SummaryStatsV2 {
  award_count: number
  avg_bid_rate: number | null
  last_award_at: string | null
  lost_count: number
}

export interface MarketDepth {
  registered: number
  env_active: number
}

export interface KpiV2 {
  pool_size: number
  market_depth: MarketDepth
  sr_count: number
  sr_pct: number
  avg_expected_price_million: number | null
  supply_risk: string
  contract_recommend: string
}

export interface ComplianceInfo {
  sr_in_top_k: number
  sr_pct_top_k: number
  obligation_threshold_pct: number
  obligation_met: boolean
}

export interface AxesV2 {
  supply_stability: number
  sr_diversity: number
  track_record: number
  price_competitiveness: number
}

export interface RecommendationV2Item {
  rank: number
  brn: string
  corp_name: string | null
  tier: string
  badges: string[]
  summary_stats: SummaryStatsV2
  expected_price: ExpectedPrice
  risk: RiskInfo
  supply_stability: SupplyStability
  recent_awards: AwardItemV2[]
  precedents: PrecedentItem[]
  charts: ChartsData
  rule_score: number
  axes: AxesV2
  ml_score: number | null
  score_used: string
  reason: string
}

export interface RecommendV2Response {
  item_keyword: string
  matched_prefix4: string[]
  cutoff_date: string
  kpi: KpiV2 | null
  compliance: ComplianceInfo | null
  recommendations: RecommendationV2Item[]
  meta: Record<string, unknown>
}

export interface MetaResponse {
  data_cutoff: string
  freshness_days: number
  stale_warning: boolean
  sources: Record<string, string>
}

// ── 대시보드 클라이언트 설정 ─────────────────────────────────────────
export interface DashboardSettings {
  sr_target: number
  top_k: number
  budget_unit: string
}

// ── V1 타입 (하위호환 유지) ─────────────────────────────────────────
export interface ItemSummary {
  item_code: string
  item_name: string
  bid_count: number
}

export interface SrFilterReq {
  require_any_sr?: boolean
  female_ceo?: boolean
  disabled_corp?: boolean
  social_corp?: boolean
}

export interface WeightVector {
  sr_diversity: number
  track_record: number
  price_competitiveness: number
  supply_stability: number
}

export interface RecommendRequest {
  item_code: string
  weights?: WeightVector
  sr_filter?: SrFilterReq
  top_k?: number
}

export interface AwardSummary {
  count: number
  total_amt: number
  avg_rate: number | null
  last_award_at: string | null
  supply_source: string
}

export interface RecommendationItem {
  rank: number
  brn: string
  corp_name: string
  composite_score: number
  axes: {
    supply_stability: number
    sr_diversity: number
    track_record: number
    risk_free: number
    cluster_fit: number
  }
  weighted_segments: Record<string, number>
  sr_badges: string[]
  award_summary: AwardSummary
  reason: string
  is_sr_demoted: boolean
}

export interface RecommendResponse {
  item_code: string
  matched_count: number
  sr_coverage_pct: number
  recommendations: RecommendationItem[]
  meta: Record<string, unknown>
}
