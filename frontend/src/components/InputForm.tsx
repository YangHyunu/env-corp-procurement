import React from 'react'
import type { SrFilterV2 } from '@/lib/types'

interface Props {
  keywords: string[]
  selectedKeyword: string
  onSelectKeyword: (k: string) => void
  srFilter: SrFilterV2
  onSrFilterChange: (f: SrFilterV2) => void
  budget: number
  onBudgetChange: (v: number) => void
  budgetUnit: string
  liveCount: number | null
  onSubmit: () => void
  loading: boolean
}

export function InputForm({
  keywords,
  selectedKeyword,
  onSelectKeyword,
  srFilter,
  onSrFilterChange,
  budget,
  onBudgetChange,
  budgetUnit,
  liveCount,
  onSubmit,
  loading,
}: Props) {
  const budgetMillions = budgetUnit === '억원' ? budget * 100 : budget
  const avgRate = 0.87
  const estPrice = Math.round(budgetMillions * avgRate)

  return (
    <aside
      style={{
        background: '#fff',
        borderRadius: 14,
        boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
        position: 'sticky',
        top: 84,
        maxHeight: 'calc(100vh - 100px)',
        overflowY: 'auto',
      }}
    >
      {/* 패널 헤더 */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid #f1f3f5',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em', margin: 0 }}>
          조회 조건
        </h2>
        <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 500 }}>
          조건 변경 시 자동 반영
        </span>
      </div>

      {/* 라이브 후보 카운터 */}
      <div
        style={{
          padding: '11px 16px',
          background: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)',
          borderBottom: '1px solid #c7d2fe',
          fontSize: 11,
          color: '#4f46e5',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: 600,
        }}
      >
        <span>조건 충족 후보</span>
        <b
          style={{
            color: '#312e81',
            fontVariantNumeric: 'tabular-nums',
            fontSize: 15,
            fontWeight: 800,
          }}
        >
          {liveCount != null ? `${liveCount} 업체` : '—'}
        </b>
      </div>

      {/* 1. 품목 */}
      <FormSection label="품목" step={1}>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {keywords.map((kw) => (
            <button
              key={kw}
              onClick={() => onSelectKeyword(kw)}
              style={{
                padding: '5px 11px',
                border: `1px solid ${selectedKeyword === kw ? '#0f172a' : '#ebedf0'}`,
                borderRadius: 999,
                fontSize: 11,
                cursor: 'pointer',
                background: selectedKeyword === kw ? '#0f172a' : '#fff',
                color: selectedKeyword === kw ? '#fff' : '#0f172a',
                fontWeight: 500,
                transition: 'all 0.15s',
                boxShadow: selectedKeyword === kw
                  ? '0 2px 6px rgba(15,23,42,0.18)'
                  : 'none',
              }}
            >
              {kw}
            </button>
          ))}
        </div>
      </FormSection>

      {/* 2. 정책 필터 */}
      <FormSection label="정책 필터" step={2}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <PolicyCheck
            label="사회적기업"
            checked={srFilter.social_corp}
            onChange={(v) => onSrFilterChange({ ...srFilter, social_corp: v })}
          />
          <PolicyCheck
            label="여성기업"
            checked={srFilter.female_ceo}
            onChange={(v) => onSrFilterChange({ ...srFilter, female_ceo: v })}
          />
          <PolicyCheck
            label="장애인기업"
            checked={srFilter.disabled_corp}
            onChange={(v) => onSrFilterChange({ ...srFilter, disabled_corp: v })}
          />
        </div>
      </FormSection>

      {/* 3. 예산 */}
      <FormSection label="예산" step={3}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            type="number"
            value={budget}
            min={1}
            onChange={(e) => onBudgetChange(Number(e.target.value))}
            style={{
              flex: 1,
              padding: '8px 11px',
              border: '1px solid #ebedf0',
              borderRadius: 8,
              fontSize: 13,
              textAlign: 'right',
              fontVariantNumeric: 'tabular-nums',
              fontWeight: 600,
              transition: 'all 0.15s',
              background: '#fff',
              outline: 'none',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#4f46e5'
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(79,70,229,0.12)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = '#ebedf0'
              e.currentTarget.style.boxShadow = 'none'
            }}
          />
          <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>{budgetUnit}</span>
        </div>
        <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 7 }}>
          평균 낙찰률 87% → 예상 {estPrice.toLocaleString()}{budgetUnit}
        </div>
      </FormSection>

      {/* 제출 버튼 */}
      <div style={{ padding: '14px 16px' }}>
        <button
          onClick={onSubmit}
          disabled={!selectedKeyword || loading}
          style={{
            width: '100%',
            padding: 11,
            background: loading ? '#a5b4fc' : '#4f46e5',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 700,
            cursor: !selectedKeyword || loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s',
            letterSpacing: '-0.01em',
            boxShadow: '0 1px 2px rgba(79,70,229,0.3)',
          }}
          onMouseEnter={(e) => {
            if (!loading && selectedKeyword) {
              e.currentTarget.style.background = '#4338ca'
              e.currentTarget.style.transform = 'translateY(-1px)'
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(79,70,229,0.3)'
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = loading ? '#a5b4fc' : '#4f46e5'
            e.currentTarget.style.transform = 'none'
            e.currentTarget.style.boxShadow = '0 1px 2px rgba(79,70,229,0.3)'
          }}
        >
          {loading ? '추천 산출 중...' : '추천 재산출'}
        </button>
      </div>
    </aside>
  )
}

function FormSection({
  label,
  step,
  children,
}: {
  label: string
  step: number
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        padding: '14px 16px',
        borderBottom: '1px solid #f1f3f5',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: '#0f172a',
          marginBottom: 10,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        <span>{label}</span>
        <span
          style={{
            background: '#eef2ff',
            color: '#4f46e5',
            padding: '2px 8px',
            borderRadius: 999,
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          {step}
        </span>
      </div>
      {children}
    </div>
  )
}

function PolicyCheck({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        padding: '8px 11px',
        border: `1px solid ${checked ? '#c7d2fe' : '#ebedf0'}`,
        borderRadius: 8,
        cursor: 'pointer',
        fontSize: 12,
        transition: 'all 0.15s',
        fontWeight: 500,
        background: checked ? '#eef2ff' : '#fff',
        boxShadow: checked ? 'inset 0 0 0 1px rgba(79,70,229,0.1)' : 'none',
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ accentColor: '#4f46e5' }}
      />
      {label}
    </label>
  )
}
