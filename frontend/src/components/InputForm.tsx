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
          품목 선택 시 자동 산출 · 그 외 조건은 다시 보기 버튼
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

      {/* 2. SR 토글 */}
      <FormSection label="SR 기업만 보기" step={2}>
        <SrToggle
          checked={srFilter.sr_only}
          onChange={(v) => onSrFilterChange({ sr_only: v })}
        />
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
          {loading ? '추천 산출 중...' : '추천 다시 보기'}
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

function SrToggle({
  checked,
  onChange,
}: {
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '10px 12px',
        border: `1px solid ${checked ? '#c7d2fe' : '#ebedf0'}`,
        borderRadius: 8,
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 500,
        background: checked ? '#eef2ff' : '#fff',
        boxShadow: checked ? 'inset 0 0 0 1px rgba(79,70,229,0.1)' : 'none',
        transition: 'all 0.15s',
      }}
    >
      <span style={{ color: '#0f172a' }}>
        {checked ? 'SR 보유 업체만' : '전체 (SR 무관)'}
      </span>
      <span
        style={{
          position: 'relative',
          width: 34,
          height: 18,
          borderRadius: 999,
          background: checked ? '#4f46e5' : '#cbd5e1',
          transition: 'background 0.15s',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: checked ? 18 : 2,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: '#fff',
            boxShadow: '0 1px 2px rgba(15,23,42,0.2)',
            transition: 'left 0.15s',
          }}
        />
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ display: 'none' }}
      />
    </label>
  )
}
