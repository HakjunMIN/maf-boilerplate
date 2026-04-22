import { useEffect } from 'react'

import { ApiClient } from '../api/client'
import type { JobResponse } from '../types/api'

interface UseJobPollerOptions {
  client: ApiClient
  jobId: string | null
  onUpdate: (job: JobResponse) => void
  onTerminal: (job: JobResponse) => void
  onError: (message: string) => void
}

export function useJobPoller({ client, jobId, onUpdate, onTerminal, onError }: UseJobPollerOptions): void {
  useEffect(() => {
    if (!jobId) {
      return undefined
    }

    let cancelled = false
    let timeoutId: number | null = null
    let pollCount = 0

    const poll = async () => {
      try {
        const job = await client.getJob(jobId)
        if (cancelled) {
          return
        }

        if (job.status === 'completed' || job.status === 'failed') {
          onTerminal(job)
          return
        }

        pollCount += 1
        onUpdate(job)

        const delay = pollCount >= 10 ? 5000 : 2000
        timeoutId = window.setTimeout(poll, delay)
      } catch (error) {
        if (!cancelled) {
          onError(error instanceof Error ? error.message : 'Polling failed')
        }
      }
    }

    void poll()

    return () => {
      cancelled = true
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [client, jobId, onError, onTerminal, onUpdate])
}