import type { ExpectedPrice, KpiV2 } from '@/lib/types'

interface Props {
  price: ExpectedPrice
  kpi: KpiV2 | null
}

export function PriceBar({ price, kpi }: Props) {
  const {
    point_million, q25_million, q75_million,
    n_samples, n_samples_overall, sigma_pp, market_diff_pp,
    is_extrapolated,
  } = price
  const marketAvg = kpi?.avg_expected_price_million ?? null

  const hasIQR = n_samples >= 3 && q25_million != null && q75_million != null
  const isExtrapolated = !!is_extrapolated
  const isSparse = !hasIQR && !isExtrapolated

  // Determine axis range
  const values = [point_million, q25_million, q75_million, marketAvg].filter(
    (v): v is number => v != null,
  )
  const minVal = Math.min(...values) * 0.92
  const maxVal = Math.max(...values) * 1.08
  const range = maxVal - minVal || 1

  function pct(v: number) {
    return `${Math.max(0, Math.min(100, ((v - minVal) / range) * 100)).toFixed(1)}%`
  }

  const axisPoints = [minVal, minVal + range * 0.33, minVal + range * 0.67, maxVal]

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <h3
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: '#0f172a',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            margin: 0,
          }}
        >
          예상 가격
        </h3>
        {/* 표본 / 외삽 안내 배지 */}
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '3px 9px',
            borderRadius: 999,
            background: isExtrapolated ? '#fee2e2' : isSparse ? '#fef3c7' : '#f1f5f9',
            color: isExtrapolated ? '#991b1b' : isSparse ? '#92400e' : '#475569',
            boxShadow: isExtrapolated
              ? 'inset 0 0 0 1px rgba(220,38,38,0.3)'
              : isSparse
                ? 'inset 0 0 0 1px rgba(217,119,6,0.25)'
                : 'none',
          }}
        >
          {isExtrapolated
            ? `거래 규모 외삽 — 신뢰도 낮음`
            : isSparse
              ? `표본 ${n_samples}건 — 점추정만`
              : `표본 ${n_samples}건`}
        </span>
      </div>

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
            background: isSparse ? '#f8fafc' : '#f1f5f9',
            height: 16,
            borderRadius: 8,
            position: 'relative',
            marginBottom: 8,
            opacity: isSparse ? 0.6 : 1,
          }}
        >
          {/* IQR 구간 — n>=3 일 때만 */}
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
                opacity: 1,
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
                추천 후보 평균
              </span>
            </div>
          )}

          {/* 이 업체 — n>=3: 굵은 라인(중앙값) / n<3: 큼지막한 dot */}
          {hasIQR ? (
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
          ) : (
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: pct(point_million),
                transform: 'translate(-50%, -50%)',
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: '#1e3a8a',
                boxShadow: '0 0 0 3px rgba(30,58,138,0.18), 0 2px 4px rgba(0,0,0,0.15)',
                opacity: 1,
                zIndex: 2,
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: -18,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  fontSize: 9,
                  color: '#1e3a8a',
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                }}
              >
                이 업체
              </span>
            </div>
          )}
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

      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 8, fontWeight: 500 }}>
        {isExtrapolated
          ? `이 업체 유사 규모 거래 부재 — 시장 평균/전체 평균으로 추정 (BRN 전체 ${n_samples_overall ?? 0}건)`
          : hasIQR
            ? `과거 유사 규모 ${n_samples}건 기준 · 구간·변동폭 산출 가능`
            : `유사 규모 ${n_samples}건 — 구간·변동폭 산출 불가, 점추정만 표시`}
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
      <b
        style={{
          color: valueColor ?? '#0f172a',
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 700,
        }}
      >
        {value}
      </b>
    </span>
  )
}
