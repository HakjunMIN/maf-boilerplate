import type { HealthResponse, JobCreateRequest, JobResponse } from '../types/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim()
  if (!trimmed) {
    return window.location.origin
  }
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed
}

export class ApiClient {
  baseUrl: string
  token: string

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl
    this.token = token
  }

  async healthz(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/v1/healthz')
  }

  async createJob(payload: JobCreateRequest): Promise<JobResponse> {
    return this.request<JobResponse>(
      '/api/v1/jobs',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      true,
    )
  }

  async getJob(jobId: string): Promise<JobResponse> {
    return this.request<JobResponse>(`/api/v1/jobs/${jobId}`, undefined, true)
  }

  private async request<T>(path: string, init?: RequestInit, requiresAuth = false): Promise<T> {
    const headers = new Headers(init?.headers)

    if (init?.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }

    if (requiresAuth) {
      const trimmedToken = this.token.trim()
      if (!trimmedToken) {
        throw new ApiError(400, 'Missing bearer token. Open configuration and add API_BEARER_TOKEN.')
      }
      headers.set('Authorization', `Bearer ${trimmedToken}`)
    }

    const url = new URL(path, `${normalizeBaseUrl(this.baseUrl)}/`)
    const response = await fetch(url, {
      ...init,
      headers,
    })

    if (!response.ok) {
      let message = `Request failed for ${path}`
      try {
        const contentType = response.headers.get('Content-Type') ?? ''
        if (contentType.includes('application/json')) {
          const payload = (await response.json()) as { detail?: string }
          message = payload.detail ?? message
        } else {
          const text = await response.text()
          if (text.trim()) {
            message = text.trim()
          }
        }
      } catch {
        // Ignore parser failures and keep fallback.
      }

      throw new ApiError(response.status, message)
    }

    return (await response.json()) as T
  }
}