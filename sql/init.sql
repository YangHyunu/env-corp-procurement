-- ============================================================
-- 한국환경공단 SR 공급망 분석 — PostgreSQL 초기 스키마
--
-- MVP 한 사이클(공고 수집 → 낙찰자 BRN 추출 → CSV join)에
-- 필요한 최소 테이블만 정의합니다.
--
-- 적용:
--   psql -U postgres -d <db_name> -f sql/init.sql
--
-- 메달리온 패턴:
--   raw_*  (Bronze) — API 응답 / CSV 원본 + 수집시각
--   stg_*  (Silver) — 정규화·dedupe·플래그
--   mart_* (Gold)   — 분석 와이드 테이블
-- ============================================================


-- ── 확장 ────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 업체명 유사도 검색용


-- ============================================================
-- Reference 테이블
-- ============================================================

-- 한국환경공단 산하 기관 코드 (2026-04-25 실측 기준)
CREATE TABLE IF NOT EXISTS ref_env_corp_dminstt (
    dminstt_cd      VARCHAR(7)  PRIMARY KEY,
    dminstt_nm      TEXT        NOT NULL,
    branch_kind     VARCHAR(20) NOT NULL,  -- '본사' / '권역본부' / '사업단'
    note            TEXT
);

INSERT INTO ref_env_corp_dminstt (dminstt_cd, dminstt_nm, branch_kind) VALUES
    ('B552584', '한국환경공단',                          '본사'),
    ('Z008653', '한국환경공단 수도권서부환경본부',        '권역본부'),
    ('Z004865', '한국환경공단 수도권동부환경본부',        '권역본부'),
    ('Z018993', '한국환경공단 충청권환경본부',            '권역본부'),
    ('Z004863', '한국환경공단 부산울산경남환경본부',      '권역본부'),
    ('Z003477', '한국환경공단 대구경북환경본부',          '권역본부'),
    ('Z004864', '한국환경공단 광주전남제주환경본부',      '권역본부'),
    ('Z042470', '한국환경공단 강원환경본부',              '권역본부'),
    ('D266078', '한국환경공단 국가물산업클러스터사업단',  '사업단'),
    ('Z042433', '한국환경공단 전북환경본부',              '권역본부')
ON CONFLICT (dminstt_cd) DO NOTHING;


-- ============================================================
-- raw 레이어 (Bronze) — API/CSV 원본 보존
-- ============================================================

-- 14번 API: 입찰공고
CREATE TABLE IF NOT EXISTS raw_g2b_bid_notice (
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    bid_ntce_no     VARCHAR(20) NOT NULL,
    bid_ntce_ord    VARCHAR(5)  NOT NULL,
    request_params  JSONB       NOT NULL,
    item_xml        TEXT        NOT NULL,
    PRIMARY KEY (fetched_at, bid_ntce_no, bid_ntce_ord)
);
CREATE INDEX IF NOT EXISTS idx_raw_bid_notice_no
    ON raw_g2b_bid_notice (bid_ntce_no);

-- 1번 API: 낙찰자
CREATE TABLE IF NOT EXISTS raw_g2b_award (
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    bid_ntce_no     VARCHAR(20) NOT NULL,
    bid_ntce_ord    VARCHAR(5)  NOT NULL,
    bid_clsfc_no    VARCHAR(10),
    rbid_no         VARCHAR(5),
    request_params  JSONB       NOT NULL,
    item_xml        TEXT        NOT NULL,
    PRIMARY KEY (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
);
CREATE INDEX IF NOT EXISTS idx_raw_award_no
    ON raw_g2b_award (bid_ntce_no);

-- 조달업체 CSV
CREATE TABLE IF NOT EXISTS raw_procurement_corp (
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    file_name       TEXT        NOT NULL,
    row_seq         BIGINT      NOT NULL,
    row_data        JSONB       NOT NULL,
    PRIMARY KEY (fetched_at, file_name, row_seq)
);


-- ============================================================
-- stg 레이어 (Silver) — 정규화 결과
-- ============================================================

-- 입찰공고 정규화
CREATE TABLE IF NOT EXISTS stg_bid_notice (
    bid_ntce_no             VARCHAR(20) NOT NULL,
    bid_ntce_ord            VARCHAR(5)  NOT NULL,
    bid_ntce_nm             TEXT        NOT NULL,
    dminstt_cd              VARCHAR(7),
    dminstt_nm              TEXT,
    ntce_instt_cd           VARCHAR(7),
    ntce_instt_nm           TEXT,
    dtil_prdct_clsfc_no     VARCHAR(10),
    dtil_prdct_clsfc_no_nm  TEXT,
    presmpt_prce            BIGINT,         -- 추정가격 (원)
    asign_bdgt_amt          BIGINT,         -- 배정예산금액 (원)
    bid_ntce_dt             TIMESTAMPTZ,
    openg_dt                TIMESTAMPTZ,
    bid_clse_dt             TIMESTAMPTZ,
    cntrct_cncls_mthd_nm    TEXT,           -- 계약체결방법 (제한경쟁/일반경쟁/수의계약 등)
    is_env_corp             BOOLEAN NOT NULL,  -- 환경공단 발주 여부
    fetched_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (bid_ntce_no, bid_ntce_ord)
);
CREATE INDEX IF NOT EXISTS idx_stg_bid_dminstt
    ON stg_bid_notice (dminstt_cd) WHERE is_env_corp;
CREATE INDEX IF NOT EXISTS idx_stg_bid_dtil_prdct
    ON stg_bid_notice (dtil_prdct_clsfc_no);

-- 낙찰자 정규화 (BRN 추출 핵심)
CREATE TABLE IF NOT EXISTS stg_award (
    bid_ntce_no             VARCHAR(20) NOT NULL,
    bid_ntce_ord            VARCHAR(5)  NOT NULL,
    bid_clsfc_no            VARCHAR(10) NOT NULL,
    rbid_no                 VARCHAR(5)  NOT NULL,
    bid_ntce_nm             TEXT,
    bidwinnr_nm             TEXT        NOT NULL,
    bidwinnr_brn            VARCHAR(10) NOT NULL,    -- 정규화된 BRN
    bidwinnr_ceo_nm         TEXT,
    bidwinnr_adrs           TEXT,
    sucsfbid_amt            BIGINT,                  -- 최종낙찰금액 (원)
    sucsfbid_rate           NUMERIC(7, 4),           -- 최종낙찰률 (%)
    prtcpt_cnum             INTEGER,                 -- 참가업체수
    rl_openg_dt             TIMESTAMPTZ,
    fnl_sucsf_date          DATE,
    dminstt_cd              VARCHAR(7),
    dminstt_nm              TEXT,
    rgst_dt                 TIMESTAMPTZ NOT NULL,
    fetched_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
);
CREATE INDEX IF NOT EXISTS idx_stg_award_brn
    ON stg_award (bidwinnr_brn);
CREATE INDEX IF NOT EXISTS idx_stg_award_dminstt
    ON stg_award (dminstt_cd);

-- 조달업체 정규화
CREATE TABLE IF NOT EXISTS stg_procurement_corp (
    brn                     VARCHAR(10) NOT NULL,
    branch_type             VARCHAR(4)  NOT NULL,    -- 본사/지사
    addr_sigungu            TEXT,
    corp_name               TEXT        NOT NULL,
    corp_name_normalized    TEXT,
    country                 TEXT,
    is_domestic             BOOLEAN     NOT NULL,
    is_headquarter          BOOLEAN     NOT NULL,
    corp_size               TEXT,
    main_industry           TEXT,
    is_manufacturer         BOOLEAN     NOT NULL,
    main_dtil_prdct_cd      VARCHAR(10),
    main_dtil_prdct_nm      TEXT,
    g2b_registered_at       DATE,
    -- SR 1차 (조달업체 CSV 기반)
    female_ceo_flag         BOOLEAN     NOT NULL,    -- ⚠️ 인증서 아닌 자동 판별
    disabled_corp_flag      BOOLEAN     NOT NULL,
    social_corp_flag        BOOLEAN     NOT NULL,
    sr_data_present         BOOLEAN     NOT NULL,
    fetched_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brn, branch_type, addr_sigungu)
);
CREATE INDEX IF NOT EXISTS idx_stg_proc_corp_brn
    ON stg_procurement_corp (brn);
CREATE INDEX IF NOT EXISTS idx_stg_proc_corp_dtil_prdct
    ON stg_procurement_corp (main_dtil_prdct_cd);


-- ============================================================
-- mart 레이어 (Gold) — 분석 와이드 테이블
--
-- 빌드 정책:
--   - ingest의 Dataset 트리거로 truncate + insert 재구축
--   - FK 강제 안 함 (재빌드 순서 의존 회피), 인덱스만 유지
--   - PK = 분석 단위: BRN 또는 (세부품명번호, BRN)
-- ============================================================

-- 업체 마스터 (BRN 단위 1행, 본사 우선 / 본사 부재 시 첫 행 fallback)
CREATE TABLE IF NOT EXISTS mart_company_master (
    brn                     VARCHAR(10) PRIMARY KEY,
    corp_name               TEXT NOT NULL,
    corp_name_normalized    TEXT,
    addr_sigungu            TEXT,                     -- 본사 우선 주소
    region_code             VARCHAR(2),               -- prtcptLmtRgnCd 매핑, MVP NULL 허용
    corp_size               TEXT,                     -- 중소/중견/대/비영리법인등기타
    main_industry           TEXT,
    is_manufacturer         BOOLEAN NOT NULL,
    main_dtil_prdct_cd      VARCHAR(10),
    main_dtil_prdct_nm      TEXT,
    g2b_registered_at       DATE,
    branch_count            INTEGER     NOT NULL DEFAULT 1,   -- 본사+지사 합산
    last_synced_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mart_company_master_dtil_prdct
    ON mart_company_master (main_dtil_prdct_cd);
CREATE INDEX IF NOT EXISTS idx_mart_company_master_name_norm
    ON mart_company_master (corp_name_normalized);
CREATE INDEX IF NOT EXISTS idx_mart_company_master_region
    ON mart_company_master (region_code);


-- 업체 SR 매트릭스 (BRN 단위 1행)
--   현재는 조달업체 CSV 1차 분류만 보유. v2에서 외부 SR API로 보강 예정.
--   ⚠️ female_ceo_flag = 대표자 성별 자동 판별 (여성기업확인서 보유 아님)
CREATE TABLE IF NOT EXISTS mart_company_sr (
    brn                     VARCHAR(10) PRIMARY KEY,
    -- 1차: 조달업체 CSV
    female_ceo_flag         BOOLEAN  NOT NULL,         -- ⚠️ 인증서 아님
    disabled_corp_flag      BOOLEAN  NOT NULL,
    social_corp_flag        BOOLEAN  NOT NULL,
    sr_data_present         BOOLEAN  NOT NULL,         -- 원본 결측 보존
    sr_count                SMALLINT NOT NULL,         -- 1차 기준 보유 SR 개수 (희소성용)
    last_synced_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mart_company_sr_count
    ON mart_company_sr (sr_count DESC);
CREATE INDEX IF NOT EXISTS idx_mart_company_sr_female
    ON mart_company_sr (brn) WHERE female_ceo_flag;
CREATE INDEX IF NOT EXISTS idx_mart_company_sr_disabled
    ON mart_company_sr (brn) WHERE disabled_corp_flag;
CREATE INDEX IF NOT EXISTS idx_mart_company_sr_social
    ON mart_company_sr (brn) WHERE social_corp_flag;


-- 품목 × 공급사 (세부품명번호, BRN) 단위 와이드 테이블
--   supply_source:
--     'csv_main'      = 조달업체 CSV 대표세부품명번호 매칭만
--     'award_history' = 1번 API 환경공단 낙찰 이력만
--     'both'          = 둘 다
CREATE TABLE IF NOT EXISTS mart_item_supply (
    dtil_prdct_clsfc_no     VARCHAR(10) NOT NULL,
    brn                     VARCHAR(10) NOT NULL,
    supply_source           TEXT        NOT NULL,
    -- 낙찰 실적 (1번 API, 환경공단 dminsttCd 10개 한정)
    award_count             INTEGER      NOT NULL DEFAULT 0,
    award_total_amt         BIGINT       NOT NULL DEFAULT 0,    -- 단위: 원
    avg_bid_rate            NUMERIC(6,3),                       -- 평균 낙찰률 % (예: 87.523)
    first_award_at          TIMESTAMPTZ,
    last_award_at           TIMESTAMPTZ,
    last_synced_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dtil_prdct_clsfc_no, brn)
);
CREATE INDEX IF NOT EXISTS idx_mart_item_supply_brn
    ON mart_item_supply (brn);
CREATE INDEX IF NOT EXISTS idx_mart_item_supply_topn
    ON mart_item_supply (dtil_prdct_clsfc_no, award_count DESC);
CREATE INDEX IF NOT EXISTS idx_mart_item_supply_active
    ON mart_item_supply (dtil_prdct_clsfc_no, brn) WHERE award_count > 0;


-- ============================================================
-- v2에서 추가될 테이블 (지금은 참고만)
-- ============================================================
--
-- mart_item_density        — 세부품명번호 단위 공급망 밀도·HHI
-- raw_g2b_opening_result   — 5번 API 개찰결과
-- raw_g2b_prepar_price     — 9번 API 복수예가
-- ref_dtil_prdct_whitelist — 환경기초시설 자재 세부품명번호 화이트리스트
-- raw_smpp_cert            — 공공구매 인증서 (여성/장애인/직접생산) → mart_company_sr 보강
-- raw_debarment            — 부정당제재 정보
