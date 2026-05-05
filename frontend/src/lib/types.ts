// API types — schemas.py 1:1 매핑
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
  // pipeline.scoring.score 결과: 5축 (price_competitiveness 제외)
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
