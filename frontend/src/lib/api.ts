import type {
  MetaResponse,
  RecommendV2Request,
  RecommendV2Response,
} from './types'

const BASE = 'http://localhost:8000'

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
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

// ── V2 엔드포인트 ────────────────────────────────────────────────────

export function fetchKeywords(): Promise<string[]> {
  return jsonFetch<string[]>('/api/v2/keywords')
}

export function fetchMeta(): Promise<MetaResponse> {
  return jsonFetch<MetaResponse>('/api/v2/meta')
}

export function fetchRecommendV2(req: RecommendV2Request): Promise<RecommendV2Response> {
  return jsonFetch<RecommendV2Response>('/api/v2/recommend', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
