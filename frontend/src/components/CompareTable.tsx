import type { RecommendationV2Item } from '@/lib/types'
import { riskLabel } from '@/lib/utils'

interface Props {
  items: RecommendationV2Item[]
}

export function CompareTable({ items }: Props) {
  if (items.length < 2) {
    return (
      <div
        style={{
          padding: '40px 22px',
          textAlign: 'center',
          color: '#94a3b8',
          fontSize: 13,
        }}
      >
        비교할 후보를 2~3개 선택하세요
      </div>
    )
  }

  const cols = items.slice(0, 3)

  // 각 행 최고값 판별
  function getBestIdx(vals: (number | null)[], higher = true): number {
    const filtered = vals
      .map((v, i) => ({ v, i }))
      .filter((x) => x.v != null) as { v: number; i: number }[]
    if (!filtered.length) return -1
    return filtered.reduce((best, x) =>
      higher ? (x.v > best.v ? x : best) : (x.v < best.v ? x : best)
    ).i
  }

  const scores = cols.map((c) => c.rule_score)
  const prices = cols.map((c) => c.expected_price.point_million)
  const awards = cols.map((c) => c.summary_stats.award_count)
  const rates = cols.map((c) => c.summary_stats.avg_bid_rate)
  const losts = cols.map((c) => c.summary_stats.lost_count)

  const bestScore = getBestIdx(scores)
  const bestPrice = getBestIdx(prices, false)
  const bestAward = getBestIdx(awards)
  const bestRate = getBestIdx(rates)
  const bestLost = getBestIdx(losts, false)

  return (
    <div style={{ padding: '16px 22px' }}>
      <h3
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: '#0f172a',
          marginBottom: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        후보 비교
      </h3>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `110px repeat(${cols.length}, 1fr)`,
          borderRadius: 10,
          overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
        }}
      >
        {/* 헤더 행 */}
        <Cell head>항목</Cell>
        {cols.map((c) => (
          <Cell key={c.brn} head>
            {c.corp_name ?? c.brn} #{c.rank}
          </Cell>
        ))}

        {/* 점수 */}
        <Cell label>점수</Cell>
        {cols.map((c, i) => (
          <Cell key={c.brn} winner={i === bestScore}>
            {i === bestScore ? <b>{c.rule_score.toFixed(2)}</b> : c.rule_score.toFixed(2)}
          </Cell>
        ))}

        {/* 예상가 */}
        <Cell label>예상가</Cell>
        {cols.map((c, i) => (
          <Cell key={c.brn} winner={i === bestPrice}>
            {i === bestPrice
              ? <b>{c.expected_price.point_million.toLocaleString()}만원</b>
              : `${c.expected_price.point_million.toLocaleString()}만원`}
          </Cell>
        ))}

        {/* 낙찰 건수 */}
        <Cell label>낙찰 건수</Cell>
        {cols.map((c, i) => (
          <Cell key={c.brn} winner={i === bestAward}>
            {i === bestAward
              ? <b>{c.summary_stats.award_count}건</b>
              : `${c.summary_stats.award_count}건`}
          </Cell>
        ))}

        {/* 평균 낙찰률 */}
        <Cell label>평균 낙찰률</Cell>
        {cols.map((c, i) => (
          <Cell key={c.brn} winner={i === bestRate}>
            {c.summary_stats.avg_bid_rate != null
              ? i === bestRate
                ? <b>{c.summary_stats.avg_bid_rate.toFixed(1)}%</b>
                : `${c.summary_stats.avg_bid_rate.toFixed(1)}%`
              : '—'}
          </Cell>
        ))}

        {/* 탈락 이력 */}
        <Cell label>탈락 이력</Cell>
        {cols.map((c, i) => (
          <Cell key={c.brn} winner={i === bestLost}>
            {i === bestLost
              ? <b>{c.summary_stats.lost_count}회</b>
              : `${c.summary_stats.lost_count}회`}
          </Cell>
        ))}

        {/* SR 인증 */}
        <Cell label>SR 인증</Cell>
        {cols.map((c) => (
          <Cell key={c.brn} winner={c.badges.length > 0}>
            {c.badges.length > 0
              ? <b>{c.badges.join(', ')}</b>
              : '—'}
          </Cell>
        ))}

        {/* 위험등급 */}
        <Cell label>위험등급</Cell>
        {cols.map((c) => {
          const grade = riskLabel(c.risk.grade)
          const isLow = grade === '낮음'
          return (
            <Cell key={c.brn} winner={isLow}>
              {isLow ? <b>{grade}</b> : grade}
            </Cell>
          )
        })}
      </div>
    </div>
  )
}

function Cell({
  children,
  head,
  label,
  winner,
}: {
  children?: React.ReactNode
  head?: boolean
  label?: boolean
  winner?: boolean
}) {
  const base: React.CSSProperties = {
    padding: '10px 12px',
    borderRight: '1px solid #f1f3f5',
    borderBottom: '1px solid #f1f3f5',
    fontSize: 11,
    fontWeight: 500,
  }

  if (head) {
    return (
      <div style={{ ...base, background: '#fafbfc', fontWeight: 700, color: '#0f172a' }}>
        {children}
      </div>
    )
  }
  if (label) {
    return (
      <div style={{ ...base, color: '#94a3b8', background: '#fafbfc', fontWeight: 600 }}>
        {children}
      </div>
    )
  }
  if (winner) {
    return (
      <div
        style={{
          ...base,
          background: 'linear-gradient(180deg, #f0fdf4 0%, #dcfce7 100%)',
        }}
      >
        <span style={{ color: '#14532d', fontWeight: 700 }}>{children}</span>
      </div>
    )
  }
  return <div style={base}>{children}</div>
}
