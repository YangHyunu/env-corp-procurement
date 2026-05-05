-- ============================================================
-- 5번 API (getOpengResultListInfoThng) — 개찰결과
-- 적용: psql -d eco -f sql/2026-05-03_opening_result.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS raw_g2b_opening (
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    bid_ntce_no     VARCHAR(20) NOT NULL,
    bid_ntce_ord    VARCHAR(5)  NOT NULL,
    bid_clsfc_no    VARCHAR(10) NOT NULL,
    rbid_no         VARCHAR(5)  NOT NULL,
    request_params  JSONB       NOT NULL,
    item_xml        TEXT        NOT NULL,
    PRIMARY KEY (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
);
CREATE INDEX IF NOT EXISTS idx_raw_opening_no
    ON raw_g2b_opening (bid_ntce_no);


CREATE TABLE IF NOT EXISTS stg_opening_result (
    bid_ntce_no             VARCHAR(20) NOT NULL,
    bid_ntce_ord            VARCHAR(5)  NOT NULL,
    bid_clsfc_no            VARCHAR(10) NOT NULL,
    rbid_no                 VARCHAR(5)  NOT NULL,
    bid_ntce_nm             TEXT,
    openg_dt                TIMESTAMPTZ,             -- 개찰일시
    prtcpt_cnum             INTEGER,                  -- 참가업체수
    progrs_div_cd_nm        TEXT NOT NULL,            -- '유찰' / '개찰완료' / '재입찰'
    rsrvtn_prce_file_yn     CHAR(1),                  -- Y/N — 9번 호출 가능 여부
    -- opengCorpInfo 파싱 결과 (g2b_common.parse_openg_corp_info)
    openg_case              TEXT NOT NULL,            -- single/multiple/negotiation/empty/malformed
    winner_name             TEXT,
    winner_brn              VARCHAR(10),              -- 정규화된 BRN
    winner_ceo_nm           TEXT,
    bid_amount              BIGINT,                   -- 1순위 투찰금액 (원)
    bid_rate                NUMERIC(7,4),             -- 1순위 투찰율 (%)
    -- 기관
    dminstt_cd              VARCHAR(7),
    dminstt_nm              TEXT,
    inpt_dt                 TIMESTAMPTZ,              -- 입력일시
    fetched_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
);
CREATE INDEX IF NOT EXISTS idx_stg_opening_progrs
    ON stg_opening_result (progrs_div_cd_nm);
CREATE INDEX IF NOT EXISTS idx_stg_opening_brn
    ON stg_opening_result (winner_brn) WHERE winner_brn IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stg_opening_dminstt
    ON stg_opening_result (dminstt_cd);
