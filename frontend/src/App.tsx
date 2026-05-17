import { useState, useEffect } from 'react'
import { Header } from '@/components/Header'
import { InputForm } from '@/components/InputForm'
import { PrecedentBanner } from '@/components/PrecedentBanner'
import { ComplianceBar } from '@/components/ComplianceBar'
import { KpiGrid } from '@/components/KpiGrid'
import { Toolbar } from '@/components/Toolbar'
import { RecommendationCard } from '@/components/RecommendationCard'
import { DetailPanel } from '@/components/DetailPanel'
import { CompareTable } from '@/components/CompareTable'
import { useKeywords, useRecommend, useLocalStorage } from '@/lib/hooks'
import type { DashboardSettings, SrFilterV2 } from '@/lib/types'

function Dashboard() {
  // ── 설정 (LocalStorage) ─────────────────────────────────────────
  const [srTarget, setSrTarget] = useLocalStorage('eco_sr_target', 20)
  const [topK, setTopK] = useLocalStorage('eco_top_k', 5)
  const [budgetUnit, setBudgetUnit] = useLocalStorage('eco_budget_unit', '만원')

  // 구버전 localStorage 마이그레이션 — '백만원' 저장값을 '만원'으로 교체
  useEffect(() => {
    if (budgetUnit === '백만원') setBudgetUnit('만원')
  }, [budgetUnit, setBudgetUnit])

  const settings: DashboardSettings = { sr_target: srTarget, top_k: topK, budget_unit: budgetUnit }

  const handleSaveSettings = (s: DashboardSettings) => {
    setSrTarget(s.sr_target)
    setTopK(s.top_k)
    setBudgetUnit(s.budget_unit)
  }

  // ── 입력 상태 ───────────────────────────────────────────────────
  const [selectedKeyword, setSelectedKeyword] = useState('')
  const [srFilter, setSrFilter] = useState<SrFilterV2>({ sr_only: false })
  const [budget, setBudget] = useState(800)

  // ── 결과 상태 ───────────────────────────────────────────────────
  const [selectedBrn, setSelectedBrn] = useState<string | null>(null)
  const [compareMode, setCompareMode] = useState(false)
  const [compareSet, setCompareSet] = useState<Set<string>>(new Set())

  // ── API 훅 ─────────────────────────────────────────────────────
  const { data: keywords = [] } = useKeywords()
  const { mutate: fetchRecommend, data: result, isPending: loading } = useRecommend()

  // 첫 키워드 자동 선택
  useEffect(() => {
    if (keywords.length > 0 && !selectedKeyword) {
      setSelectedKeyword(keywords[0])
    }
  }, [keywords, selectedKeyword])

  // 자동 초기 추천 (키워드 선택 시)
  useEffect(() => {
    if (selectedKeyword) {
      handleSubmit()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKeyword])

  const handleSubmit = () => {
    if (!selectedKeyword) return
    const budgetMillion = budgetUnit === '억원' ? budget * 100 : budget
    fetchRecommend({
      item_keyword: selectedKeyword,
      budget_million_won: budgetMillion,
      sr_filter: srFilter,
      top_k: topK,
    })
  }

  // 결과 첫 항목 자동 선택
  useEffect(() => {
    if (result?.recommendations?.length) {
      setSelectedBrn(result.recommendations[0].brn)
    }
  }, [result])

  const recs = result?.recommendations ?? []
  const selectedItem = recs.find((r) => r.brn === selectedBrn) ?? null

  // compare set
  const handleToggleCompare = (brn: string) => {
    setCompareSet((prev) => {
      const next = new Set(prev)
      if (next.has(brn)) {
        next.delete(brn)
      } else if (next.size < 3) {
        next.add(brn)
      }
      return next
    })
  }

  const compareItems = recs.filter((r) => compareSet.has(r.brn))

  // SR compliance — server 결정이 single source of truth (법정 하한 우회 방지)
  const compliance = result?.compliance ?? null

  const budgetMillion = budgetUnit === '억원' ? budget * 100 : budget
  const liveCount = result?.kpi?.pool_size ?? null

  return (
    <div style={{ minHeight: '100vh', background: '#f4f5f7' }}>
      <Header settings={settings} onSaveSettings={handleSaveSettings} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '280px 380px 1fr',
          gap: 18,
          padding: '20px 28px',
          maxWidth: 1600,
          margin: '0 auto',
          alignItems: 'start',
        }}
      >
        {/* ── 좌측: 입력 폼 ── */}
        <InputForm
          keywords={keywords}
          selectedKeyword={selectedKeyword}
          onSelectKeyword={(kw) => {
            setSelectedKeyword(kw)
          }}
          srFilter={srFilter}
          onSrFilterChange={setSrFilter}
          budget={budget}
          onBudgetChange={setBudget}
          budgetUnit={budgetUnit}
          liveCount={liveCount}
          onSubmit={handleSubmit}
          loading={loading}
        />

        {/* ── 중앙: 결과 ── */}
        <main>
          {recs.length > 0 && result ? (
            <>
              <PrecedentBanner
                keyword={selectedKeyword}
                precedents={recs[0]?.precedents ?? []}
              />

              <ComplianceBar compliance={compliance} topK={topK} />

              <KpiGrid kpi={result.kpi} budgetMillion={budgetMillion} />

              <Toolbar
                compareMode={compareMode}
                onToggleCompare={() => {
                  setCompareMode((v) => !v)
                  if (compareMode) setCompareSet(new Set())
                }}
                totalCount={result.kpi?.pool_size ?? recs.length}
                showCount={recs.length}
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {recs.map((item) => (
                  <RecommendationCard
                    key={item.brn}
                    item={item}
                    selected={!compareMode && selectedBrn === item.brn}
                    compareMode={compareMode}
                    inCompare={compareSet.has(item.brn)}
                    onSelect={() => {
                      if (!compareMode) setSelectedBrn(item.brn)
                    }}
                    onToggleCompare={() => handleToggleCompare(item.brn)}
                  />
                ))}
              </div>
            </>
          ) : (
            <div
              style={{
                display: 'flex',
                height: 320,
                alignItems: 'center',
                justifyContent: 'center',
                background: '#fff',
                borderRadius: 14,
                boxShadow: '0 1px 2px rgba(15,23,42,0.04)',
                color: '#94a3b8',
                fontSize: 13,
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {loading ? (
                <>
                  <LoadingSpinner />
                  <span>추천 산출 중...</span>
                </>
              ) : (
                <span>품목을 선택하고 추천 다시 보기를 눌러주세요</span>
              )}
            </div>
          )}
        </main>

        {/* ── 우측: 디테일 / 비교 ── */}
        {compareMode && compareItems.length >= 2 ? (
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
            <CompareTable items={compareItems} />
          </aside>
        ) : (
          <DetailPanel
            item={selectedItem}
            kpi={result?.kpi ?? null}
            onAddToCompare={() => {
              if (selectedItem) handleToggleCompare(selectedItem.brn)
            }}
            inCompare={selectedItem ? compareSet.has(selectedItem.brn) : false}
          />
        )}
      </div>
    </div>
  )
}

function LoadingSpinner() {
  return (
    <div
      style={{
        width: 24,
        height: 24,
        border: '2px solid #e0e7ff',
        borderTopColor: '#4f46e5',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }}
    />
  )
}

export default function App() {
  return <Dashboard />
}
