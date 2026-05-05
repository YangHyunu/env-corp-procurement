-- ============================================================
-- 피처 빌더 v2 — mart_features_at_bid
--
-- 학습 단위: (공고, BRN) 페어
-- Cutoff: 공고의 openg_dt (개찰일) — 그 직전까지 누적
-- Leakage 방지: stg_award.fnl_sucsf_date < cutoff_date 만 집계
--
-- DS must-fix 반영:
--   1. 9번 가격 피처 제외 (compno_mkng_dt > bid_clse_dt 케이스 23.6%)
--   2. mart_item_supply 사용 금지 — stg_award에서 직접 PIT 집계
--   3. SR Coverage @ K는 평가 단계에서 처리
-- ============================================================

DROP TABLE IF EXISTS mart_features_at_bid;

CREATE TABLE mart_features_at_bid (
    -- PK
    bid_ntce_no       VARCHAR(20) NOT NULL,
    bid_ntce_ord      VARCHAR(5)  NOT NULL,
    brn               VARCHAR(10) NOT NULL,

    -- Y 라벨 + sample weight 신호
    is_winner             BOOLEAN  NOT NULL,         -- target (1번 final_brn 일치)
    participated_in_bid   BOOLEAN  NOT NULL,         -- 5번에서 winner_brn으로 잡힘 (hard neg 식별용)

    -- A. BRN 정적
    corp_size              TEXT,
    is_manufacturer        BOOLEAN,
    region_code            VARCHAR(2),
    g2b_age_years          NUMERIC(5,2),
    female_ceo_flag        BOOLEAN,
    disabled_corp_flag     BOOLEAN,
    social_corp_flag       BOOLEAN,
    real_sr_flag           BOOLEAN,                  -- disabled OR social (female 제외)

    -- B. BRN 환경공단 누적 PIT
    env_award_count_pit       INTEGER NOT NULL DEFAULT 0,
    env_award_amt_pit         BIGINT  NOT NULL DEFAULT 0,
    env_avg_rate_pit          NUMERIC(6,3),
    env_dminstt_count_pit     SMALLINT NOT NULL DEFAULT 0,
    env_recent_1y_count_pit   INTEGER NOT NULL DEFAULT 0,
    days_since_last_award_pit INTEGER,

    -- C. BRN 응찰 패턴 PIT (5번 1순위 + 탈락)
    bid_top1_count_pit         INTEGER NOT NULL DEFAULT 0,
    bid_lost_count_pit         INTEGER NOT NULL DEFAULT 0,
    bid_lost_ratio_pit         NUMERIC(4,3),
    bid_recent_lost_count_pit  INTEGER NOT NULL DEFAULT 0,

    -- D. BRN × 품목 매칭 PIT
    brn_item_award_count_pit   INTEGER NOT NULL DEFAULT 0,
    brn_item_avg_rate_pit      NUMERIC(6,3),
    main_prdct_match           BOOLEAN NOT NULL DEFAULT false,

    -- E. BRN × 권역 PIT
    brn_dminstt_award_count_pit INTEGER NOT NULL DEFAULT 0,

    -- F. 공고 측
    presmpt_prce         BIGINT,
    asign_bdgt_amt       BIGINT,
    cntrct_cncls_mthd_nm TEXT,
    bid_month            SMALLINT,
    bid_quarter          SMALLINT,
    bid_dminstt_cd       VARCHAR(7),
    bid_dtil_prdct_no    VARCHAR(10),

    -- G. 시장 구조 PIT (그 공고 시점 그 품목)
    item_pool_density_pit       INTEGER NOT NULL DEFAULT 0,
    item_recent_unmet_pit       NUMERIC(4,3),
    item_top1_concentration_pit NUMERIC(4,3),

    -- 메타
    cutoff_date          TIMESTAMPTZ NOT NULL,         -- = bid_notice.openg_dt
    last_synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (bid_ntce_no, bid_ntce_ord, brn)
);

CREATE INDEX idx_features_winner       ON mart_features_at_bid (is_winner);
CREATE INDEX idx_features_brn          ON mart_features_at_bid (brn);
CREATE INDEX idx_features_item         ON mart_features_at_bid (bid_dtil_prdct_no);
CREATE INDEX idx_features_cutoff       ON mart_features_at_bid (cutoff_date);
