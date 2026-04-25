"""
조달업체 등록 내역 CSV 검증 스크립트.

확인 항목:
  1. SR 3컬럼 결측 패턴 (전부/일부/없음, 등록일자별, 국가별)
  2. 사업자등록번호 형태 (10자리 숫자 vs F-prefix vs 기타)
  3. 대표세부품명번호 자릿수 분포
  4. BRN 중복·본사지사·기업구분·제조업체 분포

사용법:
    python verify_procurement_corp_csv.py /path/to/조달업체등록내역.csv
"""
import argparse
import sys

import pandas as pd


SR_COLS = ["여성기업인증여부", "장애인기업인증여부", "사회적기업인증여부"]


def load_csv(path: str) -> pd.DataFrame:
    """UTF-8 → CP949 fallback."""
    for enc in ("utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype={"사업자등록번호": str})
        except UnicodeDecodeError:
            continue
    raise RuntimeError("CSV 인코딩 자동 감지 실패. utf-8/cp949 모두 실패.")


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def check_sr_missing(df: pd.DataFrame) -> None:
    section("1. SR 인증 3컬럼 결측 패턴")

    all_na = df[SR_COLS].isna().all(axis=1).sum()
    all_set = df[SR_COLS].notna().all(axis=1).sum()
    partial = len(df) - all_na - all_set

    total = len(df)
    print(f"3개 모두 결측 : {all_na:>8,}  ({all_na/total:.1%})")
    print(f"3개 모두 입력 : {all_set:>8,}  ({all_set/total:.1%})")
    print(f"부분 결측    : {partial:>8,}  ({partial/total:.1%})")

    # 컬럼별 Y/N/NaN 분포
    print("\n[컬럼별 값 분포]")
    for col in SR_COLS:
        vc = df[col].value_counts(dropna=False)
        print(f"\n  {col}")
        for k, v in vc.items():
            print(f"    {str(k):<6} {v:>8,}  ({v/total:.1%})")

    # 결측 행의 등록연도 분포
    print("\n[3개 모두 결측인 행의 나라장터등록 연도]")
    na_mask = df[SR_COLS].isna().all(axis=1)
    if na_mask.sum() > 0:
        years = df.loc[na_mask, "나라장터등록일자"].astype(str).str[:4]
        year_counts = years.value_counts().sort_index()
        print(f"  최소연도: {years.min()}, 최대연도: {years.max()}")
        print(f"  최근 5개 연도:")
        for y, c in year_counts.tail(5).items():
            print(f"    {y}: {c:,}")

    # 결측 행의 국가 분포
    print("\n[3개 모두 결측인 행의 업체국가 Top 10]")
    print(df.loc[na_mask, "업체국가"].value_counts().head(10).to_string())


def check_brn_format(df: pd.DataFrame) -> None:
    section("2. 사업자등록번호 형태")

    brn = df["사업자등록번호"].fillna("").astype(str)

    def classify(s: str) -> str:
        if not s or s == "nan":
            return "결측"
        if s.startswith("F"):
            return f"F-prefix (len={len(s)})"
        if s.isdigit():
            return f"숫자만 (len={len(s)})"
        return f"기타 (len={len(s)}, sample={s[:5]}...)"

    pattern_counts = brn.map(classify).value_counts()
    print("[전체 패턴 분포]")
    print(pattern_counts.to_string())

    # F-prefix 검증
    f_mask = brn.str.startswith("F")
    overseas = df["업체국가"] != "대한민국"

    print(f"\n[F-prefix vs 국외 업체 교차 검증]")
    print(f"  F-prefix 총 개수    : {f_mask.sum():>7,}")
    print(f"  국외 업체 총 개수    : {overseas.sum():>7,}")
    print(f"  F-prefix ∩ 국외     : {(f_mask & overseas).sum():>7,}")
    print(f"  F-prefix - 국외     : {(f_mask & ~overseas).sum():>7,}  (국내인데 F? 이상치)")
    print(f"  국외 - F-prefix     : {(overseas & ~f_mask).sum():>7,}  (국외인데 숫자? 이상치)")

    print(f"\n[F-prefix 업체의 국가 분포 Top 10]")
    print(df.loc[f_mask, "업체국가"].value_counts().head(10).to_string())


def check_dtil_prdct(df: pd.DataFrame) -> None:
    section("3. 대표세부품명번호 형식")

    prdct = df["대표세부품명번호"].dropna()
    print(f"non-null : {len(prdct):,} / {len(df):,}  ({len(prdct)/len(df):.1%})")

    # int 변환 (float NaN 이미 제거됨)
    prdct_int = prdct.astype("int64")
    print(f"min : {prdct_int.min():>12,}")
    print(f"max : {prdct_int.max():>12,}")

    print("\n[자릿수 분포]")
    digit_counts = prdct_int.astype(str).str.len().value_counts().sort_index()
    for d, c in digit_counts.items():
        print(f"  {d}자리 : {c:>8,}")

    print("\n[10자리 zero-pad 샘플]")
    samples = prdct_int.head(10).map(lambda x: f"{x:010d}")
    for s in samples:
        print(f"  {s}")


def check_integrity(df: pd.DataFrame) -> None:
    section("4. 추가 무결성 체크")

    # BRN 중복
    n_total = len(df)
    n_unique_brn = df["사업자등록번호"].nunique()
    print(f"전체 행      : {n_total:>8,}")
    print(f"unique BRN   : {n_unique_brn:>8,}")
    print(f"중복 (행 - BRN): {n_total - n_unique_brn:>8,}")

    if n_total != n_unique_brn:
        print("\n[같은 BRN 여러 행 — Top 5]")
        dup = df.groupby("사업자등록번호").size().sort_values(ascending=False).head(5)
        for brn, cnt in dup.items():
            sample_name = df.loc[df["사업자등록번호"] == brn, "업체명"].iloc[0]
            print(f"  {brn} ({cnt}행) — {sample_name}")

    print("\n[본사지사구분]")
    print(df["본사지사구분"].value_counts(dropna=False).to_string())

    print("\n[기업구분]")
    print(df["기업구분"].value_counts(dropna=False).head(10).to_string())

    print("\n[제조업체여부]")
    print(df["제조업체여부"].value_counts(dropna=False).to_string())

    print("\n[업체국가 Top 10]")
    print(df["업체국가"].value_counts().head(10).to_string())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("csv_path", help="조달업체 등록 내역 CSV 경로")
    args = p.parse_args()

    print(f"📂 로드 중: {args.csv_path}")
    df = load_csv(args.csv_path)
    print(f"✅ {len(df):,} 행 × {df.shape[1]} 컬럼")

    check_sr_missing(df)
    check_brn_format(df)
    check_dtil_prdct(df)
    check_integrity(df)

    print("\n" + "=" * 70)
    print("검증 완료.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
