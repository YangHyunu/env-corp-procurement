-- 환경 도메인 풀 확장 — stg_bid_notice 에 agency_tier 컬럼 추가.
-- env_corp (한국환경공단 10) / env_domain (수자원공사·광역상수도·환경부 산하 26) / other.
-- pipeline.g2b_common.agency_tier_for() 가 dminstt_cd → tier 매핑.

ALTER TABLE stg_bid_notice
    ADD COLUMN IF NOT EXISTS agency_tier VARCHAR(16);

-- 인덱스 (recommend_v2 의 retrieve / brn_env_stats / market_baseline 쿼리 가속)
CREATE INDEX IF NOT EXISTS idx_stg_bid_notice_agency_tier
    ON stg_bid_notice (agency_tier);

COMMENT ON COLUMN stg_bid_notice.agency_tier IS
    'env_corp | env_domain | other — see pipeline.g2b_common.agency_tier_for';
