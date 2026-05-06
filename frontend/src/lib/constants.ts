// 도메인 상수 — pipeline/policy.py 와 동기화 필요
//
// SR_LEGAL_FLOOR_PCT: 사회적가치 우선구매 의무비율 법정 하한.
//   조달사업법 시행령 제24조. backend pipeline/policy.py SR_LEGAL_FLOOR_PCT 와 동일 값.
//   UI 옵션은 절대 이 값 미만으로 노출하지 않는다 (사용자가 법정 기준을 우회하지 못하도록).

export const SR_LEGAL_FLOOR_PCT = 20

export const SR_TARGET_OPTIONS = [SR_LEGAL_FLOOR_PCT, 30, 40, 50] as const

export const TOPK_OPTIONS = [3, 5, 10] as const
