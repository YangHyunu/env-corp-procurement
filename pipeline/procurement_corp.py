"""
procurement_corp.py — 조달업체 등록 내역 CSV 처리.

대상 파일: data.go.kr/15053474 (UI-ADOAAA-008R)
형식: UTF-16, 탭 구분, 약 64만 행

주의사항:
- 여성기업인증여부는 대표자 주민번호 기반 자동 판별 (인증서 보유 X)
- SR 3컬럼 결측은 'N'으로 정규화하되 sr_data_present 플래그로 보존
- BRN 중복 = 본사+지사 구조 → (BRN, 본사지사구분, 시군구) 복합키
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from .g2b_common import normalize_brn, normalize_corp_name

logger = logging.getLogger(__name__)


# ── 컬럼 매핑 (한글 → snake_case) ─────────────────────────
COL_RENAME: dict[str, str] = {
    "업체명":           "corp_name",
    "사업자등록번호":    "brn",
    "업체소재시군구":    "addr_sigungu",
    "본사지사구분":      "branch_type",
    "업체국가":          "country",
    "기업구분":          "corp_size",
    "대표업종":          "main_industry",
    "제조업체여부":      "is_manufacturer",
    "대표세부품명번호":  "main_dtil_prdct_cd",
    "대표세부품명":      "main_dtil_prdct_nm",
    "나라장터등록일자":  "g2b_registered_at",
    "여성기업인증여부":  "female_ceo_flag",     # 인증서 아닌 자동 판별!
    "장애인기업인증여부": "disabled_corp_flag",
    "사회적기업인증여부": "social_corp_flag",
}

SR_COLS: list[str] = ["female_ceo_flag", "disabled_corp_flag", "social_corp_flag"]


# ── 로딩 ───────────────────────────────────────────────
def load(path: str | Path) -> pd.DataFrame:
    """원본 CSV 로드 (UTF-16 + 탭).

    이 파일 한정 인코딩·구분자. 다른 공공 CSV는 별도 검증 필요.
    """
    df = pd.read_csv(
        path,
        encoding="utf-16",
        sep="\t",
        dtype={"사업자등록번호": str},
    )
    return df.rename(columns=COL_RENAME)


# ── 정규화 ─────────────────────────────────────────────
def _pad_dtil_prdct(x) -> str | None:
    """대표세부품명번호 float → 10자리 문자열."""
    if pd.isna(x):
        return None
    return f"{int(x):010d}"


def _yyyymmdd_to_date(x) -> date | None:
    """8자리 정수/문자열 → date. 포맷 오류 시 None."""
    if pd.isna(x):
        return None
    s = str(int(x)) if isinstance(x, (int, float)) else str(x).strip()
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """raw → 정규화된 DataFrame."""
    out = df.copy()

    # BRN 정규화 (F-prefix 포함)
    out["brn"] = out["brn"].map(normalize_brn)

    # 업체명 정규화 (검색용 보조 컬럼)
    out["corp_name_normalized"] = out["corp_name"].map(normalize_corp_name)

    # 품명번호 float → 10자리 zero-pad 문자열
    out["main_dtil_prdct_cd"] = out["main_dtil_prdct_cd"].map(_pad_dtil_prdct)

    # 등록일자 8자리 int → date
    out["g2b_registered_at"] = out["g2b_registered_at"].map(_yyyymmdd_to_date)

    # SR 데이터 존재 플래그 (3개 모두 결측이면 False)
    out["sr_data_present"] = out[SR_COLS].notna().any(axis=1)

    # SR 정규화: 결측 → N → bool
    for col in SR_COLS:
        out[col] = (
            out[col].fillna("N").map({"Y": True, "N": False}).astype(bool)
        )

    # 부울 정규화
    out["is_manufacturer"] = (
        out["is_manufacturer"].map({"Y": True, "N": False}).astype(bool)
    )
    out["is_headquarter"] = out["branch_type"] == "본사"
    out["is_domestic"] = out["country"] == "대한민국"

    # 유효 BRN만 보존 (정규화에서 None 된 행 = 이상치 제거)
    n_before = len(out)
    out = out[out["brn"].notna()].copy()
    n_dropped = n_before - len(out)
    if n_dropped:
        logger.info("BRN 정규화 실패로 %d 행 제거", n_dropped)

    return out


# ── 분석 필터링 ─────────────────────────────────────────
def filter_for_analysis(
    df: pd.DataFrame,
    *,
    domestic_only: bool = True,
    headquarter_only: bool = True,
    manufacturer_only: bool = False,
) -> pd.DataFrame:
    """분석 모집단 필터링."""
    mask = pd.Series(True, index=df.index)
    if domestic_only:
        mask &= df["is_domestic"]
    if headquarter_only:
        mask &= df["is_headquarter"]
    if manufacturer_only:
        mask &= df["is_manufacturer"]
    return df[mask].copy()
