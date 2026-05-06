import type { ExpectedPrice, KpiV2 } from '@/lib/types'

interface Props {
  price: ExpectedPrice
  kpi: KpiV2 | null
}

export function PriceBar({ price, kpi }: Props) {
  const { point_million, q25_million, q75_million, n_samples, sigma_pp, market_diff_pp } = price
  const marketAvg = kpi?.avg_expected_price_million ?? null

  const hasIQR = n_samples >= 3 && q25_million != null && q75_million != null

  // Determine axis range
  const values = [
    point_million,
    q25_million,
    q75_million,
    marketAvg,
  ].filter((v): v is number => v != null)

  const minVal = Math.min(...values) * 0.92
  const maxVal = Math.max(...values) * 1.08
  const range = maxVal - minVal || 1

  function pct(v: number) {
    return `${Math.max(0, Math.min(100, ((v - minVal) / range) * 100)).toFixed(1)}%`
  }

  const axisPoints = [minVal, minVal + range * 0.33, minVal + range * 0.67, maxVal]

  return (
    <div>
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
        예상 가격
      </h3>

      <div style={{ padding: '6px 0 8px' }}>
        {/* 축 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 10,
            color: '#94a3b8',
            padding: '0 4px',
            marginBottom: 6,
            fontWeight: 500,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {axisPoints.map((v, i) => (
            <span key={i}>{Math.round(v)}</span>
          ))}
        </div>

        {/* 막대 */}
        <div
          style={{
            background: '#f1f5f9',
            height: 16,
            borderRadius: 8,
            position: 'relative',
            marginBottom: 8,
          }}
        >
          {/* IQR 구간 */}
          {hasIQR && (
            <div
              style={{
                position: 'absolute',
                height: 16,
                left: pct(q25_million!),
                width: `${((q75_million! - q25_million!) / range) * 100}%`,
                background: 'linear-gradient(180deg, #93c5fd 0%, #60a5fa 100%)',
                borderRadius: 8,
                boxShadow: '0 1px 2px rgba(59,130,246,0.3)',
              }}
            />
          )}

          {/* 시장 평균 마커 */}
          {marketAvg != null && (
            <div
              style={{
                position: 'absolute',
                top: -5,
                bottom: -5,
                width: 2,
                left: pct(marketAvg),
                background: '#ef4444',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  bottom: -18,
                  left: -10,
                  fontSize: 9,
                  color: '#ef4444',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                유사 발주 평균
              </span>
            </div>
          )}

          {/* 이 업체 중앙값 */}
          <div
            style={{
              position: 'absolute',
              top: -3,
              bottom: -3,
              width: 3,
              left: pct(point_million),
              background: '#1e3a8a',
              borderRadius: 2,
              boxShadow: '0 0 0 1px rgba(255,255,255,0.7)',
            }}
          >
            <span
              style={{
                position: 'absolute',
                top: -16,
                left: -16,
                fontSize: 9,
                color: '#1e3a8a',
                fontWeight: 700,
                whiteSpace: 'nowrap',
              }}
            >
              이 업체
            </span>
          </div>
        </div>
      </div>

      {/* 통계 */}
      <div
        style={{
          display: 'flex',
          gap: 18,
          fontSize: 11,
          marginTop: 22,
          flexWrap: 'wrap',
        }}
      >
        <StatItem label="예상가" value={`${point_million.toLocaleString()}백만`} />
        {hasIQR && (
          <StatItem
            label="구간(50%)"
            value={`${q25_million!.toLocaleString()}~${q75_million!.toLocaleString()}`}
          />
        )}
        {sigma_pp != null && (
          <StatItem
            label="낙찰률 변동폭"
            value={`${sigma_pp < 3 ? '낮음' : sigma_pp < 6 ? '보통' : '높음'} (${sigma_pp.toFixed(1)}%p)`}
          />
        )}
        {market_diff_pp != null && (
          <StatItem
            label="유사 발주 평균 대비"
            value={`${market_diff_pp >= 0 ? '+' : ''}${market_diff_pp.toFixed(1)}%p`}
            valueColor={market_diff_pp <= 0 ? '#15803d' : '#dc2626'}
          />
        )}
      </div>

      <div style={{ fontSize: 10, color: '#6b7280', marginTop: 8 }}>
        {n_samples >= 3
          ? `과거 ${n_samples}건 낙찰 기준 · 표본 ${n_samples}건`
          : `표본 ${n_samples}건 (IQR 표시 불가)`}
      </div>
    </div>
  )
}

function StatItem({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <span>
      <span style={{ color: '#94a3b8', fontWeight: 500 }}>{label}</span>{' '}
      <b style={{ color: valueColor ?? '#0f172a', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
        {value}
      </b>
    </span>
  )
}
