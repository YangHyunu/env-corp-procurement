import { useState } from 'react'
import { ItemSearch } from '@/components/ItemSearch'
import { RecommendList } from '@/components/RecommendList'
import type { ItemSummary } from '@/lib/types'

export default function App() {
  const [item, setItem] = useState<ItemSummary | null>(null)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-7xl items-baseline justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold">ECO 추천 대시보드</h1>
            <p className="text-xs text-muted-foreground">
              환경공단 관급자재 SR 공급망 분석 — MVP 수직 슬라이스
            </p>
          </div>
          <span className="text-xs text-muted-foreground">v0.1.0</span>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[320px_1fr]">
        <aside>
          <h2 className="mb-2 text-sm font-medium">품목 검색</h2>
          <ItemSearch selected={item} onSelect={setItem} />
        </aside>

        <section>
          {item ? (
            <>
              <div className="mb-4">
                <h2 className="text-sm font-medium">
                  {item.item_name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {item.item_code}
                  </span>
                </h2>
              </div>
              <RecommendList itemCode={item.item_code} topK={5} />
            </>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
              왼쪽에서 품목을 선택하세요
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
