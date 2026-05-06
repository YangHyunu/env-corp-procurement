import { useState, useRef, useEffect } from 'react'
import { Settings } from 'lucide-react'
import { useMeta } from '@/lib/hooks'
import type { DashboardSettings } from '@/lib/types'
import { SR_LEGAL_FLOOR_PCT, SR_TARGET_OPTIONS, TOPK_OPTIONS } from '@/lib/constants'

interface Props {
  settings: DashboardSettings
  onSaveSettings: (s: DashboardSettings) => void
}

export function Header({ settings, onSaveSettings }: Props) {
  const { data: meta } = useMeta()
  const [open, setOpen] = useState(false)
  const popRef = useRef<HTMLDivElement>(null)

  const [draft, setDraft] = useState(settings)

  useEffect(() => {
    setDraft(settings)
  }, [settings])

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const isStale = meta?.stale_warning ?? true
  const freshnessText = meta
    ? `기준일 ${meta.data_cutoff} (${meta.freshness_days}일 전)`
    : '데이터 확인 중...'

  return (
    <header
      style={{
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'saturate(150%) blur(8px)',
        borderBottom: '1px solid #ebedf0',
        padding: '14px 28px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <div>
        <h1 style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em', margin: 0 }}>
          ECO 추천 대시보드
        </h1>
        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 3, fontWeight: 500 }}>
          환경공단 관급자재 — 공고 전 후보 탐색
        </div>
      </div>

      <div style={{ display: 'flex', gap: 14, alignItems: 'center', position: 'relative' }}>
        {/* Freshness pill */}
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            fontSize: 11,
            padding: '5px 12px',
            borderRadius: 999,
            fontWeight: 500,
            transition: 'background-color 0.2s',
            background: isStale ? '#fef2f2' : '#f0fdf4',
            color: isStale ? '#b91c1c' : '#15803d',
            boxShadow: isStale ? 'inset 0 0 0 1px #fecaca' : 'inset 0 0 0 1px #bbf7d0',
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              flexShrink: 0,
              background: isStale ? '#ef4444' : '#22c55e',
              boxShadow: isStale
                ? '0 0 0 3px rgba(239,68,68,0.15)'
                : '0 0 0 3px rgba(34,197,94,0.15)',
            }}
            className={isStale ? 'animate-pulse-dot' : ''}
          />
          {meta
            ? (isStale
              ? `데이터 갱신 지연 — ${freshnessText}`
              : `데이터 최신 — ${freshnessText}`)
            : '데이터 확인 중...'}
        </span>

        {/* Settings button */}
        <div ref={popRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setOpen((v) => !v)}
            aria-label="설정"
            style={{
              fontSize: 11,
              padding: '5px 12px',
              border: '1px solid #ebedf0',
              background: '#fff',
              borderRadius: 8,
              cursor: 'pointer',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#fafbfc'
              e.currentTarget.style.borderColor = '#d4d8de'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#fff'
              e.currentTarget.style.borderColor = '#ebedf0'
            }}
          >
            <Settings size={12} />
            설정
          </button>

          {open && (
            <div
              className="animate-pop-in"
              style={{
                position: 'absolute',
                top: 38,
                right: 0,
                width: 290,
                background: '#fff',
                border: '1px solid #ebedf0',
                borderRadius: 14,
                boxShadow: '0 12px 28px rgba(15,23,42,0.08), 0 4px 8px rgba(15,23,42,0.04)',
                padding: 14,
                zIndex: 20,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: '#0f172a',
                  marginBottom: 12,
                  paddingBottom: 10,
                  borderBottom: '1px solid #f1f3f5',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                기관 기본값 (브라우저 저장)
              </div>

              <SettingsRow label="SR 의무비율 기본값">
                <select
                  value={draft.sr_target}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, sr_target: Number(e.target.value) }))
                  }
                  style={selectStyle}
                >
                  {SR_TARGET_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {v}%{v === SR_LEGAL_FLOOR_PCT ? ' (법정)' : ''}
                    </option>
                  ))}
                </select>
              </SettingsRow>

              <SettingsRow label="추천 Top K">
                <select
                  value={draft.top_k}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, top_k: Number(e.target.value) }))
                  }
                  style={selectStyle}
                >
                  {TOPK_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </SettingsRow>

              <SettingsRow label="예산 단위">
                <select
                  value={draft.budget_unit}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, budget_unit: e.target.value }))
                  }
                  style={selectStyle}
                >
                  <option>백만원</option>
                  <option>억원</option>
                </select>
              </SettingsRow>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  paddingTop: 10,
                  borderTop: '1px solid #f1f3f5',
                }}
              >
                <button
                  onClick={() => {
                    onSaveSettings(draft)
                    setOpen(false)
                  }}
                  style={{
                    padding: '6px 16px',
                    background: '#4f46e5',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  저장
                </button>
                <span style={{ fontSize: 10, color: '#6b7280', marginLeft: 'auto' }}>
                  localStorage 에 저장됨
                </span>
              </div>
            </div>
          )}
        </div>

        <span style={{ fontSize: 10, color: '#9ca3af' }}>v2.2</span>
      </div>
    </header>
  )
}

function SettingsRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 10,
        marginBottom: 10,
        fontSize: 12,
      }}
    >
      <span style={{ color: '#475569' }}>{label}</span>
      {children}
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '5px 8px',
  border: '1px solid #ebedf0',
  borderRadius: 6,
  fontSize: 12,
  background: '#fff',
  cursor: 'pointer',
}
