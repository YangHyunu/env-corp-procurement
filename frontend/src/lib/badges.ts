import type { CSSProperties } from 'react'
import { tierLabel } from './utils'

// ── 디자인 토큰: Tier / SR / 위험등급 색상 ─────────────────────────
// 원본 4개 컴포넌트(RecommendationCard / DetailPanel / RiskAndStability)에
// 흩어져 있던 색상 dict 의 단일 정의.

export const TIER_COLORS: Record<string, CSSProperties> = {
  A: { background: '#dcfce7', color: '#15803d' },
  B: { background: '#dbeafe', color: '#1e40af' },
  C: { background: '#f1f5f9', color: '#475569' },
}

export const SR_BADGE_COLORS: Record<string, CSSProperties> = {
  여성기업: { background: '#fce7f3', color: '#be185d' },
  장애인기업: { background: '#fef3c7', color: '#92400e' },
  사회적기업: { background: '#d1fae5', color: '#065f46' },
}

export const SR_BADGE_FALLBACK: CSSProperties = {
  background: '#ede9fe',
  color: '#6d28d9',
}

// 위험등급(riskLabel 출력값 기준): 낮음 / 보통 / 주의 / 미확인
export const RISK_GRADE_COLORS: Record<string, CSSProperties> = {
  낮음: {
    background: '#dcfce7',
    color: '#15803d',
    boxShadow: 'inset 0 0 0 1px rgba(34,197,94,0.25)',
  },
  보통: {
    background: '#fef3c7',
    color: '#92400e',
    boxShadow: 'inset 0 0 0 1px rgba(217,119,6,0.25)',
  },
  주의: {
    background: '#fee2e2',
    color: '#991b1b',
    boxShadow: 'inset 0 0 0 1px rgba(220,38,38,0.25)',
  },
  미확인: {
    background: '#f1f5f9',
    color: '#475569',
    boxShadow: 'inset 0 0 0 1px #e2e8f0',
  },
}

// ── 공용 컴포넌트 ────────────────────────────────────────────────
const BADGE_BASE: CSSProperties = {
  fontSize: 9,
  padding: '2px 7px',
  borderRadius: 5,
  fontWeight: 700,
  letterSpacing: '0.01em',
}

interface TierBadgeProps {
  tier: string
}

export function TierBadge({ tier }: TierBadgeProps) {
  const style = TIER_COLORS[tier] ?? TIER_COLORS.C
  return (
    <span style={{ ...BADGE_BASE, ...style }}>
      {tierLabel(tier)}
    </span>
  )
}

interface SrBadgeProps {
  label: string
}

export function SrBadge({ label }: SrBadgeProps) {
  const style = SR_BADGE_COLORS[label] ?? SR_BADGE_FALLBACK
  return (
    <span style={{ ...BADGE_BASE, ...style }}>
      {label}
    </span>
  )
}
