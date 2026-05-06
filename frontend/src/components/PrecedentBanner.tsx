import type { PrecedentItem } from '@/lib/types'

interface Props {
  keyword: string
  precedents: PrecedentItem[]
}

export function PrecedentBanner({ keyword, precedents }: Props) {
  if (!precedents || precedents.length === 0) return null

  // 업체별 빈도 집계
  const countMap = new Map<string, { name: string; count: number }>()
  for (const p of precedents) {
    if (!p.bidwinnr_brn) continue
    const key = p.bidwinnr_brn
    const name = p.winner_corp_name ?? p.bidwinnr_brn
    const existing = countMap.get(key)
    countMap.set(key, { name, count: (existing?.count ?? 0) + 1 })
  }

  const sorted = Array.from(countMap.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, 4)

  const total = precedents.length

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #fef3c7 0%, #fffbeb 100%)',
        borderRadius: 10,
        padding: '12px 14px',
        marginBottom: 14,
        fontSize: 11,
        lineHeight: 1.65,
        boxShadow:
          '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05), inset 0 0 0 1px rgba(217,119,6,0.15)',
      }}
    >
      <span
        style={{
          display: 'block',
          fontSize: 10,
          color: '#92400e',
          marginBottom: 4,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        최근 12개월 유사 발주 ({keyword})
      </span>
      <b style={{ color: '#92400e', fontWeight: 700 }}>{total}건</b> 발주
      {sorted.map((s, i) => (
        <span key={s.name}>
          {' '}— {s.name}{' '}
          <b style={{ color: '#92400e', fontWeight: 700 }}>
            {s.count}건({Math.round((s.count / total) * 100)}%)
          </b>
          {i < sorted.length - 1 ? '' : ' · 기타'}
        </span>
      ))}
    </div>
  )
}
