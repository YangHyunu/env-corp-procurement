"""
8개 자연어 키워드 → (prefix4, name_regex) 매핑.

(다) prefix4 + 품목명 regex 정책.
4710 공유 키워드들이 진짜로 다른 풀을 가리키도록 disambiguate.

각 키워드 풀 크기 (환경공단 활동 BRN 기준, 2026-05 시점):
  하수처리용 펌프   108
  대기오염 측정장비 104
  수질측정센서       81
  폐수처리약품       22
  슬러지 탈수기      16
  활성탄 필터        15
  바이오가스 발전기  10
  소각로 내화벽돌    2~3 (데이터 한계)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordFilter:
    prefix4: list[str]
    name_regex: str  # PostgreSQL ~ 연산자에 그대로 사용


KEYWORD_FILTERS: dict[str, KeywordFilter] = {
    "하수처리용 펌프":   KeywordFilter(["4015"],                   r"펌프"),
    "슬러지 탈수기":     KeywordFilter(["4710"],                   r"탈수|디캔터|벨트프레스|스크루프레스"),
    "소각로 내화벽돌":   KeywordFilter(["4710", "4010"],           r"소각|내화|벽돌|보일러"),
    "바이오가스 발전기": KeywordFilter(["2611"],                   r"발전|가스엔진|바이오"),
    "수질측정센서":      KeywordFilter(["4110", "4111", "4617"],   r"수질|시료|센서"),
    "대기오염 측정장비": KeywordFilter(["4111"],                   r"대기|오염|가스|배기"),
    "폐수처리약품":      KeywordFilter(["4710", "2411"],           r"폐수|약품|화학|응집|중화"),
    "활성탄 필터":       KeywordFilter(["4710"],                   r"활성탄|여과|필터"),
    # — env_domain 확장 키워드 (수자원공사·상수도·환경부 산하 발주 매칭) —
    "상하수도 배관":     KeywordFilter(["4014", "4016"],           r"강관|이음관|관로|배관|상수관|하수관"),
    "분석 시약·시료":    KeywordFilter(["1216"],                   r"시약|시료|질소|기준|표준액"),
    "실험실 측정기기":   KeywordFilter(["4112", "4111"],           r"실험실|희석기|배양기|분석기|크로마토|분광"),
}

KEYWORDS: list[str] = list(KEYWORD_FILTERS.keys())


def resolve(keyword: str) -> KeywordFilter:
    """키워드 → (prefix4, regex). 매핑 실패 시 ValueError."""
    if keyword not in KEYWORD_FILTERS:
        raise ValueError(
            f"unknown keyword: {keyword!r}. supported: {KEYWORDS}"
        )
    return KEYWORD_FILTERS[keyword]
