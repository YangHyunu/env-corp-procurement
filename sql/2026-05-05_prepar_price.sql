-- ============================================================
-- 9번 API (getOpengResultListInfoThngPreparPcDetail) — 복수예가 상세
-- 적용: psql -d eco -f sql/2026-05-05_prepar_price.sql
--
-- 한 공고당 15개 예가 row.
-- raw/stg는 row 그대로, mart에서 공고 단위 1행으로 집계.
-- ============================================================

-- ── raw (15 row per bid) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_g2b_prepar (
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    bid_ntce_no     VARCHAR(20) NOT NULL,
    bid_ntce_ord    VARCHAR(5)  NOT NULL,
    bid_clsfc_no    VARCHAR(10) NOT NULL,
    rbid_no         VARCHAR(5)  NOT NULL,
    prce_sno        SMALLINT    NOT NULL,    -- 예가 일련번호 1~15
    request_params  JSONB       NOT NULL,
    item_xml        TEXT        NOT NULL,
    PRIMARY KEY (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, prce_sno)
);
CREATE INDEX IF NOT EXISTS idx_raw_prepar_no ON raw_g2b_prepar (bid_ntce_no);


-- ── stg (15 row per bid, 정규화) ────────────────────────────
CREATE TABLE IF NOT EXISTS stg_prepar_price (
    bid_ntce_no             VARCHAR(20) NOT NULL,
    bid_ntce_ord            VARCHAR(5)  NOT NULL,
    bid_clsfc_no            VARCHAR(10) NOT NULL,
    rbid_no                 VARCHAR(5)  NOT NULL,
    prce_sno                SMALLINT    NOT NULL,    -- 1~15
    bsis_plnprc             BIGINT,                   -- 개별 예가 가격
    drwt_yn                 CHAR(1),                  -- Y/N (추첨됨)
    drwt_num                INTEGER,                  -- 추첨 번호
    -- 공고 단위 정보 (모든 row 동일하지만 편의상 같이)
    plnprc                  BIGINT,                   -- 추첨 4개 평균 = 최종 예정가격
    bssamt                  BIGINT,                   -- 기초가격
    bssamt_bss_up_num       SMALLINT,                 -- 기초가격 ± n%
    compno_mkng_dt          TIMESTAMPTZ,              -- 예가 작성일
    rl_openg_dt             TIMESTAMPTZ,
    fetched_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, prce_sno)
);
CREATE INDEX IF NOT EXISTS idx_stg_prepar_drwt
    ON stg_prepar_price (bid_ntce_no, bid_ntce_ord) WHERE drwt_yn='Y';


-- ── mart (공고 1건 = 1 row, 집계) ───────────────────────────
CREATE TABLE IF NOT EXISTS mart_bid_prepar (
    bid_ntce_no             VARCHAR(20) NOT NULL,
    bid_ntce_ord            VARCHAR(5)  NOT NULL,
    plnprc                  BIGINT,                   -- 최종 예정가격 (추첨 4개 평균)
    bssamt                  BIGINT,                   -- 기초가격
    bssamt_bss_up_num       SMALLINT,                 -- 기초가격 ± n%
    -- 15개 예가 분포 통계
    n_prces                 SMALLINT,                 -- 보통 15
    n_drawn                 SMALLINT,                 -- 보통 4
    bsis_min                BIGINT,
    bsis_max                BIGINT,
    bsis_mean               NUMERIC(20,2),
    bsis_std                NUMERIC(20,2),
    bsis_range_pct          NUMERIC(6,3),             -- (max-min)/mean*100 — 발주 불확실성
    drawn_snos              SMALLINT[],               -- 추첨된 일련번호 4개
    compno_mkng_dt          TIMESTAMPTZ,
    last_synced_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bid_ntce_no, bid_ntce_ord)
);
