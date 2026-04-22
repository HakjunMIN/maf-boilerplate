import { useMemo, useReducer } from 'react'

import { ApiClient, ApiError } from './api/client'
import { ConfigPanel } from './components/ConfigPanel'
import { HealthBadge } from './components/HealthBadge'
import { JobForm } from './components/JobForm'
import { JobView } from './components/JobView'
import { useConfig } from './hooks/useConfig'
import { useJobPoller } from './hooks/useJobPoller'
import type { JobCreateRequest, JobResponse } from './types/api'
import './App.css'

type AppPhase = 'idle' | 'submitting' | 'polling' | 'done' | 'error'

interface AppState {
  phase: AppPhase
  job: JobResponse | null
  message: string | null
}

type AppAction =
  | { type: 'SUBMIT' }
  | { type: 'JOB_CREATED'; job: JobResponse }
  | { type: 'JOB_UPDATED'; job: JobResponse }
  | { type: 'JOB_TERMINAL'; job: JobResponse }
  | { type: 'ERROR'; message: string; job?: JobResponse | null }
  | { type: 'RESET' }

const initialState: AppState = {
  phase: 'idle',
  job: null,
  message: null,
}

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SUBMIT':
      return { phase: 'submitting', job: null, message: null }
    case 'JOB_CREATED':
      return { phase: 'polling', job: action.job, message: null }
    case 'JOB_UPDATED':
      return { ...state, phase: 'polling', job: action.job, message: null }
    case 'JOB_TERMINAL':
      return {
        phase: 'done',
        job: action.job,
        message: action.job.error_message,
      }
    case 'ERROR':
      return {
        phase: 'error',
        job: action.job ?? state.job,
        message: action.message,
      }
    case 'RESET':
      return initialState
    default:
      return state
  }
}

function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message} (${error.status})`
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Unexpected error'
}

function App() {
  const { config, setConfig } = useConfig()
  const [state, dispatch] = useReducer(reducer, initialState)
  const client = useMemo(() => new ApiClient(config.baseUrl, config.token), [config.baseUrl, config.token])
  const activeJobId = state.phase === 'polling' && state.job ? state.job.job_id : null

  useJobPoller({
    client,
    jobId: activeJobId,
    onUpdate: (job) => dispatch({ type: 'JOB_UPDATED', job }),
    onTerminal: (job) => dispatch({ type: 'JOB_TERMINAL', job }),
    onError: (message) => dispatch({ type: 'ERROR', message }),
  })

  async function handleSubmit(payload: JobCreateRequest): Promise<void> {
    dispatch({ type: 'SUBMIT' })
    try {
      const job = await client.createJob(payload)
      if (job.status === 'completed' || job.status === 'failed') {
        dispatch({ type: 'JOB_TERMINAL', job })
        return
      }
      dispatch({ type: 'JOB_CREATED', job })
    } catch (error) {
      dispatch({ type: 'ERROR', message: toUserMessage(error) })
    }
  }

  const isBusy = state.phase === 'submitting' || state.phase === 'polling'

  return (
    <div className="app-shell">
      <div className="app-grid" aria-hidden="true" />
      <header className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">MAF Lab Console</p>
          <h1>Reasoning jobs, sandbox traces, and web research in one operator view.</h1>
          <p className="hero-text">
            Submit a prompt to the backend orchestrator, track the async job lifecycle, and inspect exactly what the agent produced.
          </p>
        </div>
        <div className="hero-status-card">
          <HealthBadge client={client} />
          <div className="hero-metrics">
            <div>
              <span>Mode</span>
              <strong>{config.baseUrl.trim() ? 'Direct API' : 'Proxy / Same Origin'}</strong>
            </div>
            <div>
              <span>Token</span>
              <strong>{config.token.trim() ? 'Loaded' : 'Missing'}</strong>
            </div>
          </div>
        </div>
      </header>

      <main className="main-stack">
        <ConfigPanel config={config} onChange={setConfig} />
        <JobForm onSubmit={handleSubmit} disabled={isBusy} />

        {state.message ? (
          <section className="message-banner" role="alert">
            <span className="message-label">Notice</span>
            <p>{state.message}</p>
          </section>
        ) : null}

        {state.job ? (
          <JobView
            job={state.job}
            isBusy={state.phase === 'polling'}
            onReset={() => dispatch({ type: 'RESET' })}
          />
        ) : (
          <section className="empty-panel">
            <p className="empty-lead">No active job yet</p>
            <p className="empty-body">
              Start with a prompt that requires reasoning, file analysis, or external lookup. The result view will appear here as the backend job progresses.
            </p>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
