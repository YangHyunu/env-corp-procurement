import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function fmtMillion(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${n.toLocaleString()}백만`
}

export function fmtAmt(krw: number | null | undefined): string {
  if (krw == null) return '—'
  const million = Math.round(krw / 1_000_000)
  if (million >= 1000) return `${(million / 1000).toFixed(1)}억`
  return `${million}백만`
}

export function fmtPct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—'
  return `${v.toFixed(decimals)}%`
}

export function tierLabel(tier: string): string {
  if (tier === 'A') return 'A등급'
  if (tier === 'B') return 'B등급'
  if (tier === 'C') return '검토대상'
  return tier
}

export function riskLabel(grade: string): string {
  if (grade === '안전') return '낮음'
  if (grade === '양호') return '보통'
  if (grade === '주의') return '주의'
  return '미확인'
}

export function badgeKey(b: string): string {
  const map: Record<string, string> = {
    '여성기업': 'sr-female',
    '장애인기업': 'sr-disabled',
    '사회적기업': 'sr-social',
  }
  return map[b] ?? 'region'
}
