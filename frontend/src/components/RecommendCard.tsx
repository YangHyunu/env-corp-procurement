import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { RecommendationItem } from '@/lib/types'

const AXIS_LABEL: Record<keyof RecommendationItem['axes'], string> = {
  sr_diversity: 'SR 다양성',
  track_record: '낙찰 실적',
  supply_stability: '공급 안정',
  risk_free: '리스크 無',
  cluster_fit: '군집 적합',
}

function fmtKRW(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}억`
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}만`
  return n.toLocaleString()
}

export function RecommendCard({ item }: { item: RecommendationItem }) {
  const radarData = (Object.keys(AXIS_LABEL) as Array<keyof typeof AXIS_LABEL>).map((k) => ({
    axis: AXIS_LABEL[k],
    value: item.axes[k],
  }))

  const award = item.award_summary

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs text-muted-foreground">#{item.rank}</div>
            <CardTitle className="truncate text-base">{item.corp_name}</CardTitle>
            <div className="text-xs text-muted-foreground">BRN {item.brn}</div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold tabular-nums">
              {item.composite_score.toFixed(3)}
            </div>
            <div className="text-xs text-muted-foreground">composite</div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-3">
        <div className="h-44 w-full">
          <ResponsiveContainer>
            <RadarChart data={radarData} outerRadius="75%">
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10 }} />
              <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
              <Radar
                dataKey="value"
                stroke="var(--chart-2)"
                fill="var(--chart-2)"
                fillOpacity={0.3}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-wrap gap-1">
          {item.sr_badges.length === 0 ? (
            <Badge variant="outline">SR 없음</Badge>
          ) : (
            item.sr_badges.map((b) => (
              <Badge key={b} variant="secondary">
                {b}
              </Badge>
            ))
          )}
          {item.is_sr_demoted ? (
            <Badge variant="destructive">SR floor demoted</Badge>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-muted-foreground">낙찰 건수</div>
            <div className="tabular-nums">{award.count}건</div>
          </div>
          <div>
            <div className="text-muted-foreground">총 낙찰액</div>
            <div className="tabular-nums">{fmtKRW(award.total_amt)}원</div>
          </div>
          <div>
            <div className="text-muted-foreground">평균 낙찰률</div>
            <div className="tabular-nums">
              {award.avg_rate == null ? '—' : `${award.avg_rate.toFixed(1)}%`}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">최근 낙찰일</div>
            <div className="tabular-nums">
              {award.last_award_at ?? '—'}
            </div>
          </div>
        </div>

        {item.reason ? (
          <p className="text-xs text-muted-foreground">{item.reason}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
