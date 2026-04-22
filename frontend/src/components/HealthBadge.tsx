import { useEffect, useState } from 'react'

import { ApiClient } from '../api/client'

type HealthState = 'healthy' | 'degraded' | 'offline'

interface HealthBadgeProps {
  client: ApiClient
}

export function HealthBadge({ client }: HealthBadgeProps) {
  const [state, setState] = useState<HealthState>('offline')
  const [label, setLabel] = useState('Backend unreachable')

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const result = await client.healthz()
        if (!cancelled) {
          setState(result.status === 'ok' ? 'healthy' : 'degraded')
          setLabel(result.app)
        }
      } catch {
        if (!cancelled) {
          setState('offline')
          setLabel('Backend unreachable')
        }
      }
    }

    void check()
    const intervalId = window.setInterval(() => {
      void check()
    }, 30000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [client])

  return (
    <div className={`health-badge health-badge--${state}`}>
      <span className="health-badge__dot" aria-hidden="true" />
      <div>
        <p className="health-badge__state">{state}</p>
        <p className="health-badge__label">{label}</p>
      </div>
    </div>
  )
}