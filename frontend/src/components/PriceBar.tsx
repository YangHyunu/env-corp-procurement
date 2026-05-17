import type { ExpectedPrice, KpiV2 } from '@/lib/types'

interface Props {
  price: ExpectedPrice
  kpi: KpiV2 | null
  budgetMillion: number
}

export function PriceBar({ price, kpi, budgetMillion }: Props) {
  const {
    point_million, q25_million, q75_million,
    n_samples, n_samples_overall, sigma_pp, market_diff_pp,
    is_extrapolated,
  } = price
  const marketAvgMillion = kpi?.avg_expected_price_million ?? null

  const hasIQR = n_samples >= 3 && q25_million != null && q75_million != null
  const isExtrapolated = !!is_extrapolated
  const isSparse = !hasIQR && !isExtrapolated

  // ── 가격 → 낙찰률 역산 (budget 알면 가능) ─────────────────
  const canDeriveRate = budgetMillion > 0
  const pointRate = canDeriveRate ? (point_million / budgetMillion) * 100 : null
  const q25Rate = canDeriveRate && q25_million != null
    ? (q25_million / budgetMillion) * 100 : null
  const q75Rate = canDeriveRate && q75_million != null
    ? (q75_million / budgetMillion) * 100 : null
  const marketRate = canDeriveRate && marketAvgMillion != null
    ? (marketAvgMillion / budgetMillion) * 100 : null

  // 막대 축 범위 — 낙찰률 75~100 기본, 데이터 범위가 더 넓으면 확장
  const rateValues = [pointRate, q25Rate, q75Rate, marketRate].filter(
    (v): v is number => v != null,
  )
  const minVal = rateValues.length ? Math.min(75, Math.floor(Math.min(...rateValues) - 2)) : 75
  const maxVal = rateValues.length ? Math.max(100, Math.ceil(Math.max(...rateValues) + 2)) : 100
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
          예상 낙찰률
        </h3>
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
            ? `유사 거래 부족 — 신뢰도 낮음`
            : isSparse
              ? `표본 ${n_samples}건 — 단일 추정값만`
              : `표본 ${n_samples}건`}
        </span>
      </div>

      {/* 메인 숫자: 점추정 낙찰률 */}
      <div
        style={{
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: '#0f172a',
          marginBottom: 4,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {pointRate != null ? `${pointRate.toFixed(1)}%` : '—'}
      </div>
      {hasIQR && q25Rate != null && q75Rate != null && (
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 14, fontWeight: 500 }}>
          구간(50%) {q25Rate.toFixed(1)}~{q75Rate.toFixed(1)}%
        </div>
      )}

      {/* 막대 — 낙찰률 축 */}
      <div style={{ padding: '6px 0 8px' }}>
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
            <span key={i}>{v.toFixed(0)}%</span>
          ))}
        </div>

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
          {/* IQR */}
          {hasIQR && q25Rate != null && q75Rate != null && (
            <div
              style={{
                position: 'absolute',
                height: 16,
                left: pct(q25Rate),
                width: `${((q75Rate - q25Rate) / range) * 100}%`,
                background: 'linear-gradient(180deg, #93c5fd 0%, #60a5fa 100%)',
                borderRadius: 8,
                boxShadow: '0 1px 2px rgba(59,130,246,0.3)',
              }}
            />
          )}

          {/* 시장 평균 마커 */}
          {marketRate != null && (
            <div
              style={{
                position: 'absolute',
                top: -5,
                bottom: -5,
                width: 2,
                left: pct(marketRate),
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
                추천 후보 평균
              </span>
            </div>
          )}

          {/* 이 업체 */}
          {pointRate != null && (hasIQR ? (
            <div
              style={{
                position: 'absolute',
                top: -3,
                bottom: -3,
                width: 3,
                left: pct(pointRate),
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
                left: pct(pointRate),
                transform: 'translate(-50%, -50%)',
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: '#1e3a8a',
                boxShadow: '0 0 0 3px rgba(30,58,138,0.18), 0 2px 4px rgba(0,0,0,0.15)',
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
          ))}
        </div>
      </div>

      {/* 보조 통계 */}
      <div
        style={{
          display: 'flex',
          gap: 18,
          fontSize: 11,
          marginTop: 22,
          flexWrap: 'wrap',
        }}
      >
        {sigma_pp != null && (
          <StatItem
            label="변동폭"
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

      {/* 예상 가격 보조 캡션 */}
      {pointRate != null && canDeriveRate && (
        <div
          style={{
            fontSize: 11,
            color: '#475569',
            marginTop: 12,
            padding: '8px 10px',
            background: '#f8fafc',
            borderRadius: 6,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          예산 {budgetMillion.toLocaleString()}만원 × {pointRate.toFixed(1)}% ≈{' '}
          <b>{point_million.toLocaleString()}만원</b>
          <div
            style={{
              fontSize: 10,
              color: '#94a3b8',
              marginTop: 4,
              fontWeight: 500,
            }}
          >
            ※ 단순 비례 추정 — 가격 회귀 모델 도입 전 임시
          </div>
        </div>
      )}

      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 8, fontWeight: 500 }}>
        {isExtrapolated
          ? `이 업체 유사 규모 거래 부재 — 시장 평균/전체 평균으로 추정 (BRN 전체 ${n_samples_overall ?? 0}건)`
          : hasIQR
            ? `과거 유사 규모 ${n_samples}건 기준 · 구간·변동폭 산출 가능`
            : `유사 규모 ${n_samples}건 — 구간·변동폭 산출 불가, 단일 추정값만 표시`}
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
