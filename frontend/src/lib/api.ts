import type {
  ItemSummary,
  RecommendRequest,
  RecommendResponse,
} from './types'

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    let detail: string
    try {
      const body = (await res.json()) as { detail?: string }
      detail = body.detail ?? res.statusText
    } catch {
      detail = res.statusText
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

export function listItems(q: string, limit = 20): Promise<ItemSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q) params.set('q', q)
  return jsonFetch<ItemSummary[]>(`/api/items?${params.toString()}`)
}

export function recommend(req: RecommendRequest): Promise<RecommendResponse> {
  return jsonFetch<RecommendResponse>('/api/recommend', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
