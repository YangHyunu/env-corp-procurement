"""
Single-source legal/policy constants.

사회적 가치 우선구매 촉진법 제7조: 공공기관은 사회적기업 등으로부터 일정 비율 이상
재화·서비스를 구매해야 한다 (현행 20%).
법령 개정 시 이 모듈 한 곳만 수정.
"""
from __future__ import annotations

SR_LEGAL_FLOOR_PCT: float = 20.0
SR_LEGAL_FLOOR_FRACTION: float = SR_LEGAL_FLOOR_PCT / 100.0

assert abs(SR_LEGAL_FLOOR_FRACTION * 100.0 - SR_LEGAL_FLOOR_PCT) < 1e-9
