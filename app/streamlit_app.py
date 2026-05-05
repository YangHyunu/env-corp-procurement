"""
ECO Streamlit 대시보드 — 환경공단 SR 공급망 분석

실행:
  uv run streamlit run app/streamlit_app.py

탭 3개:
  ① EDA 탐색 — 유찰률·vendor lock-in·repeat profile·cold pool
  ② 업체 상세 — BRN 입력 → 낙찰이력·SR·5번 시장활동
  ③ 추천 (placeholder) — score v2 완성 후 활성화
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.express as px
import psycopg2
import psycopg2.extras
import streamlit as st
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))
DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")


# ── 페이지 기본 ─────────────────────────────────────────────
st.set_page_config(
    page_title="ECO 공급망 대시보드",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── DB 헬퍼 ────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def db_query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    with psycopg2.connect(DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    return pd.DataFrame(db_query(sql, params))


# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌊 ECO 공급망 대시보드")
    st.caption("한국환경공단 환경기초시설 관급자재 SR 분석")
    st.divider()
    try:
        ok = db_query("SELECT 1 AS ok")[0]["ok"]
        st.success(f"DB 연결 OK · {DSN}")
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        st.stop()

    st.divider()
    st.caption("데이터 기준일: **2026-05-03**")
    st.caption("환경공단 5년치 (2021Q2~2026Q2)")


# ── 탭 ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["① EDA 탐색", "② 업체 상세", "③ 추천 (준비중)"])


# ════════════════════════════════════════════════════════════
# 탭 ①  EDA 탐색
# ════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## EDA 탐색")
    st.caption("환경공단 5년치 입찰·낙찰·개찰결과로 잡은 신호들")

    # ── KPI ────────────────────────────────────────────────
    kpi = db_query("""
        SELECT
          (SELECT COUNT(*) FROM stg_award) AS awards,
          (SELECT COUNT(*) FROM stg_opening_result) AS opening,
          (SELECT COUNT(*) FROM stg_opening_result WHERE progrs_div_cd_nm='유찰') AS rebid,
          (SELECT COUNT(DISTINCT brn) FROM mart_company_master) AS brns
    """)[0]
    rebid_pct = 100.0 * kpi["rebid"] / max(kpi["opening"], 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("환경공단 낙찰", f"{kpi['awards']:,}", "5년 누적")
    c2.metric("개찰결과 (5번)", f"{kpi['opening']:,}", "신규 적재")
    c3.metric("유찰", f"{kpi['rebid']:,}", f"{rebid_pct:.1f}%")
    c4.metric("BRN 마스터", f"{kpi['brns']:,}", "조달업체 풀")

    st.divider()

    # ── 1. 권역별 유찰률 ────────────────────────────────
    st.markdown("### 1. 권역별 유찰률")
    st.caption("환경공단 10개 권역의 유찰 빈도. 높을수록 공급망이 얇음.")

    rebid_by_region = df("""
        WITH env AS (
          SELECT o.dminstt_cd, o.progrs_div_cd_nm
          FROM stg_opening_result o
          JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
          WHERE bn.is_env_corp
        )
        SELECT d.dminstt_nm AS 권역,
               COUNT(*) AS 전체,
               SUM(CASE WHEN progrs_div_cd_nm='유찰' THEN 1 ELSE 0 END) AS 유찰,
               ROUND(100.0*SUM(CASE WHEN progrs_div_cd_nm='유찰' THEN 1 ELSE 0 END)
                     /COUNT(*)::numeric, 1) AS 유찰률_pct
        FROM env e JOIN ref_env_corp_dminstt d USING (dminstt_cd)
        GROUP BY 1 ORDER BY 유찰률_pct DESC
    """)

    cL, cR = st.columns([2, 1])
    with cL:
        fig = px.bar(
            rebid_by_region.sort_values("유찰률_pct"),
            x="유찰률_pct", y="권역", orientation="h",
            text="유찰률_pct", color="유찰률_pct",
            color_continuous_scale="Reds",
            labels={"유찰률_pct": "유찰률 (%)"},
        )
        fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0),
                          coloraxis_showscale=False)
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with cR:
        st.dataframe(rebid_by_region, hide_index=True, use_container_width=True)

    st.info(
        "**의미** — 충청권·수도권서부·부산울산경남이 15% 이상으로 높음. "
        "이 권역의 자주 유찰되는 품목은 공급사 풀이 얇으니, "
        "추천 시 SR 조건을 완화해 후보군을 넓혀야 함."
    )

    st.divider()

    # ── 2. Vendor lock-in 품목 ──────────────────────────
    st.markdown("### 2. Vendor lock-in 의심 품목")
    st.caption("한 회사가 같은 품목 낙찰을 50% 이상 점유하는 케이스 (누적 낙찰 ≥5건)")

    lockin = df("""
        WITH item_total AS (
          SELECT dtil_prdct_clsfc_no AS code, SUM(award_count) AS total_w
          FROM mart_item_supply WHERE award_count>0 GROUP BY 1
        ),
        ranked AS (
          SELECT mis.dtil_prdct_clsfc_no AS code, mis.brn, mis.award_count AS w,
                 it.total_w,
                 ROW_NUMBER() OVER (PARTITION BY mis.dtil_prdct_clsfc_no
                                    ORDER BY mis.award_count DESC) AS rk
          FROM mart_item_supply mis JOIN item_total it ON it.code = mis.dtil_prdct_clsfc_no
          WHERE mis.award_count > 0
        )
        SELECT r.code AS 품목코드,
               LEFT(MAX(bn.dtil_prdct_clsfc_no_nm), 22) AS 품목명,
               r.total_w AS 전체낙찰,
               r.w AS top1_낙찰,
               ROUND((r.w::float/r.total_w)::numeric, 2) AS top1_점유율,
               LEFT(MAX(m.corp_name), 20) AS top1_업체
        FROM ranked r
        LEFT JOIN stg_bid_notice bn ON bn.dtil_prdct_clsfc_no = r.code
        LEFT JOIN mart_company_master m ON m.brn = r.brn
        WHERE r.rk=1 AND r.total_w>=5 AND r.w::float/r.total_w>=0.5
        GROUP BY r.code, r.brn, r.w, r.total_w
        ORDER BY r.total_w DESC
    """)
    st.dataframe(lockin, hide_index=True, use_container_width=True)
    st.info(
        "**의미** — 점유율 50%+는 사실상 단독 공급. 추천 점수에서 가산이 아닌 "
        "'경쟁 부재 경고'로 표시할 후보."
    )

    st.divider()

    # ── 3. Repeat winner 프로파일 ──────────────────────
    st.markdown("### 3. Repeat winner 프로파일 비교")
    st.caption("환경공단 낙찰 횟수에 따라 회사 특성이 어떻게 다른가")

    profile = df("""
        WITH winners AS (
          SELECT bidwinnr_brn AS brn, COUNT(*) AS aw FROM stg_award GROUP BY 1
        )
        SELECT
          CASE WHEN aw=1 THEN 'oneshot (1회)'
               WHEN aw<=3 THEN 'occasional (2-3)'
               ELSE 'heavy (4+)' END AS 그룹,
          COUNT(*) AS BRN수,
          ROUND(AVG(CASE WHEN m.is_manufacturer THEN 1.0 ELSE 0.0 END)::numeric*100, 0) AS mfg_pct,
          ROUND(AVG(CASE WHEN s.disabled_corp_flag OR s.social_corp_flag
                         THEN 1.0 ELSE 0.0 END)::numeric*100, 0) AS real_sr_pct,
          ROUND(AVG(EXTRACT(YEAR FROM AGE(now(), m.g2b_registered_at)))::numeric, 1) AS avg_yrs
        FROM winners w
        LEFT JOIN mart_company_master m ON m.brn = w.brn
        LEFT JOIN mart_company_sr s ON s.brn = w.brn
        GROUP BY 1 ORDER BY MIN(aw)
    """)
    cL, cR = st.columns([1, 1])
    with cL:
        profile_disp = profile.rename(columns={
            "brn수": "BRN수", "mfg_pct": "제조업 %",
            "real_sr_pct": "실질SR %", "avg_yrs": "평균 업력(년)",
        })
        st.dataframe(profile_disp, hide_index=True, use_container_width=True)
    with cR:
        melted = profile.melt(id_vars=["그룹"],
                              value_vars=["mfg_pct", "real_sr_pct"],
                              var_name="지표", value_name="비율")
        melted["지표"] = melted["지표"].map({"mfg_pct": "제조업 %",
                                              "real_sr_pct": "실질SR %"})
        fig = px.bar(melted, x="그룹", y="비율", color="지표",
                     barmode="group", text="비율")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**의미** — 낙찰 많이 받는 회사일수록 제조업·실질SR·업력이 모두 높음. "
        "score v2의 'mfg + tenure + real_sr' 트리오가 repeat 신호."
    )

    st.divider()

    # ── 4. Cold pool 살려낸 SR ──────────────────────────
    st.markdown("### 4. Cold pool에서 살려낸 SR 업체 ⭐")
    st.caption("환경공단 낙찰 0건이라 noise 취급되던 회사 중 5번 API로 활동 발견")

    cold = db_query("""
        WITH env_bidders AS (
          SELECT DISTINCT o.winner_brn AS brn
          FROM stg_opening_result o
          JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
          WHERE bn.is_env_corp AND o.winner_brn IS NOT NULL
        ),
        non_winners AS (
          SELECT eb.brn FROM env_bidders eb
          LEFT JOIN stg_award a ON a.bidwinnr_brn=eb.brn
          WHERE a.bidwinnr_brn IS NULL
        )
        SELECT COUNT(*) AS bid_only,
               SUM(CASE WHEN m.brn IS NOT NULL THEN 1 ELSE 0 END) AS in_master,
               SUM(CASE WHEN s.sr_count>0 THEN 1 ELSE 0 END) AS with_sr
        FROM non_winners n
        LEFT JOIN mart_company_master m USING (brn)
        LEFT JOIN mart_company_sr s USING (brn)
    """)[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("입찰 활동했지만 낙찰 0", f"{cold['bid_only']:,}",
              "지금까지 cold(noise)")
    c2.metric("마스터 DB 등록", f"{cold['in_master']:,}",
              f"{100*cold['in_master']/cold['bid_only']:.0f}%")
    c3.metric("SR 인증 보유 ⭐", f"{cold['with_sr']:,}",
              "score v2가 살릴 후보")

    rev = df("""
        WITH env_bidders AS (
          SELECT DISTINCT o.winner_brn AS brn
          FROM stg_opening_result o
          JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
          WHERE bn.is_env_corp AND o.winner_brn IS NOT NULL
        ),
        non_winners AS (
          SELECT eb.brn FROM env_bidders eb
          LEFT JOIN stg_award a ON a.bidwinnr_brn=eb.brn
          WHERE a.bidwinnr_brn IS NULL
        )
        SELECT n.brn AS BRN,
               LEFT(m.corp_name, 24) AS 업체명,
               m.corp_size AS 규모,
               m.is_manufacturer AS 제조,
               s.sr_count AS SR수,
               (CASE WHEN s.female_ceo_flag THEN 'F' ELSE '' END ||
                CASE WHEN s.disabled_corp_flag THEN 'D' ELSE '' END ||
                CASE WHEN s.social_corp_flag THEN 'S' ELSE '' END) AS 인증
        FROM non_winners n
        LEFT JOIN mart_company_master m USING (brn)
        LEFT JOIN mart_company_sr s USING (brn)
        WHERE s.sr_count>0
        ORDER BY s.sr_count DESC NULLS LAST
        LIMIT 50
    """)
    with st.expander(f"SR 보유 업체 상위 50곳 (총 {cold['with_sr']:,}곳 중)"):
        st.dataframe(rev, hide_index=True, use_container_width=True)
        st.caption("BRN을 복사해 ② 업체 상세 탭에서 조회 가능")


# ════════════════════════════════════════════════════════════
# 탭 ②  업체 상세
# ════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## 업체 상세")
    st.caption("BRN 10자리를 입력하면 회사 정보·낙찰이력·5번 시장활동을 보여줍니다")

    brn_input = st.text_input(
        "BRN (사업자등록번호 10자리)",
        value=st.session_state.get("brn_input", ""),
        max_chars=10,
        placeholder="예: 1408121883",
    )

    if not brn_input:
        st.info("BRN을 입력하세요. (탭 ①의 'SR 보유 업체' 표에서 복사)")
        st.stop()

    if not (brn_input.isdigit() and len(brn_input) == 10) and \
       not (brn_input.startswith("F") and len(brn_input) == 10):
        st.error("BRN은 10자리 숫자 (또는 F + 9자리) 형식이어야 합니다.")
        st.stop()

    head = db_query("""
        SELECT m.brn, m.corp_name, m.corp_size, m.addr_sigungu,
               m.is_manufacturer, m.g2b_registered_at, m.main_industry,
               s.sr_count, s.female_ceo_flag, s.disabled_corp_flag, s.social_corp_flag
        FROM mart_company_master m
        JOIN mart_company_sr s USING (brn)
        WHERE m.brn = %s
    """, (brn_input,))

    if not head:
        st.error(f"BRN {brn_input}을 마스터 DB에서 찾을 수 없습니다.")
        st.stop()

    h = head[0]

    # 헤더
    st.markdown(f"### {h['corp_name']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BRN", h["brn"])
    c2.metric("규모", h["corp_size"] or "-")
    c3.metric("제조업", "Y" if h["is_manufacturer"] else "N")
    yrs = ""
    if h["g2b_registered_at"]:
        from datetime import date
        yrs = f"{(date(2026,5,3) - h['g2b_registered_at']).days // 365}년"
    c4.metric("나라장터 업력", yrs or "-")

    badges = []
    if h["female_ceo_flag"]:    badges.append("🟡 여성기업(자동판별)")
    if h["disabled_corp_flag"]: badges.append("🟢 장애인기업")
    if h["social_corp_flag"]:   badges.append("🔵 사회적기업")
    st.markdown(" · ".join(badges) if badges else "_SR 인증 없음_")
    st.caption(f"📍 {h['addr_sigungu'] or '-'}  ·  업종: {h['main_industry'] or '-'}")

    st.divider()

    # 낙찰 이력 + 5번 활동
    cL, cR = st.columns(2)

    with cL:
        st.markdown("#### 환경공단 낙찰 이력 (1번 API)")
        awards = df("""
            SELECT a.fnl_sucsf_date::text AS 낙찰일,
                   LEFT(a.bid_ntce_nm, 28) AS 공고명,
                   a.dminstt_nm AS 발주처,
                   a.sucsfbid_amt AS 금액,
                   a.sucsfbid_rate AS 낙찰률
            FROM stg_award a
            WHERE a.bidwinnr_brn = %s
            ORDER BY a.fnl_sucsf_date DESC NULLS LAST
            LIMIT 50
        """, (brn_input,))
        if awards.empty:
            st.warning("환경공단 낙찰 이력 없음")
        else:
            tot = db_query("""
                SELECT COUNT(*) AS n, COALESCE(SUM(sucsfbid_amt),0)::bigint AS amt
                FROM stg_award WHERE bidwinnr_brn = %s
            """, (brn_input,))[0]
            st.caption(f"총 **{tot['n']}건 / {tot['amt']/1e8:.2f}억원**")
            st.dataframe(awards, hide_index=True, use_container_width=True,
                         height=320)

    with cR:
        st.markdown("#### 환경공단 시장활동 (5번 API ⭐)")
        market = df("""
            WITH env AS (
              SELECT o.*, bn.is_env_corp
              FROM stg_opening_result o
              JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
              WHERE bn.is_env_corp AND o.winner_brn = %s
            )
            SELECT progrs_div_cd_nm AS 결과,
                   COUNT(*) AS 건수,
                   ROUND(AVG(bid_rate)::numeric, 2) AS 평균투찰률
            FROM env GROUP BY 1 ORDER BY 건수 DESC
        """, (brn_input,))
        if market.empty:
            st.warning("환경공단 5번 입찰 활동 없음 (1순위 투찰 이력 X)")
        else:
            st.dataframe(market, hide_index=True, use_container_width=True)

            # 권역별 활동
            region = df("""
                SELECT d.dminstt_nm AS 권역, COUNT(*) AS 건수
                FROM stg_opening_result o
                JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
                JOIN ref_env_corp_dminstt d ON d.dminstt_cd = o.dminstt_cd
                WHERE bn.is_env_corp AND o.winner_brn = %s
                GROUP BY 1 ORDER BY 건수 DESC
            """, (brn_input,))
            if not region.empty:
                fig = px.bar(region, x="건수", y="권역", orientation="h",
                             text="건수")
                fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════
# 탭 ③  추천 (Placeholder)
# ════════════════════════════════════════════════════════════
with tab3:
    st.markdown("## 추천 (top-K)")
    st.warning(
        "🚧 **Score v2 설계 중 — 활성화 예정**  \n"
        "기존 v1은 환경공단 낙찰 685페어(전체 1%)에서만 작동해 cold-start 폭증. "
        "이번 EDA로 v2 5축 설계 합의됨."
    )
    st.markdown("### Score v2 설계 (5축)")
    v2 = pd.DataFrame([
        {"차원": "repeat_strength", "데이터": "1번 API",
         "의미": "환경공단 낙찰 누적 + 권역 다양성 가중"},
        {"차원": "bid_activity ⭐", "데이터": "5번 API",
         "의미": "입찰만 한 BRN까지 포함 → cold pool 신호"},
        {"차원": "negotiation_loss ⭐", "데이터": "1번 vs 5번 비교",
         "의미": "1순위 자주 떨어지는 회사 디스카운트"},
        {"차원": "unmet_demand_item ⭐", "데이터": "5번 유찰 카운트",
         "의미": "품목 차원: 자주 유찰되는 품목 = SR 조건 완화"},
        {"차원": "real_sr_flag", "데이터": "mart_company_sr",
         "의미": "여성기업(자동판별) 제외, 장애·사회만 binary"},
    ])
    st.dataframe(v2, hide_index=True, use_container_width=True)

    st.markdown("### 다음 작업")
    st.markdown("""
    1. `pipeline/scoring_v2.py` — 5축 정규화 + composite + tiebreaker
    2. 가중치 슬라이더 UI (이 탭에서)
    3. 결과 카드: 레이더 차트 + SR 뱃지 + 낙찰이력 + 시장활동
    """)
