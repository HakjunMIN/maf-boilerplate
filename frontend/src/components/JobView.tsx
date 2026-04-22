import type { JobResponse } from '../types/api'
import { ResultTabs } from './ResultTabs'

interface JobViewProps {
  job: JobResponse
  isBusy: boolean
  onReset: () => void
}

export function JobView({ job, isBusy, onReset }: JobViewProps) {
  return (
    <section className="panel panel--result">
      <div className="result-header">
        <div>
          <p className="section-kicker">Active job</p>
          <h2>{job.query}</h2>
        </div>
        <div className="result-header__meta">
          <span className={`status-pill status-pill--${job.status}`}>{job.status}</span>
          <button className="ghost-button" type="button" onClick={onReset} disabled={isBusy}>
            Clear view
          </button>
        </div>
      </div>

      <dl className="job-meta-grid">
        <div>
          <dt>Job ID</dt>
          <dd>{job.job_id}</dd>
        </div>
        <div>
          <dt>Input files</dt>
          <dd>{job.input_files.length > 0 ? job.input_files.join(', ') : 'None'}</dd>
        </div>
      </dl>

      <ResultTabs job={job} />
    </section>
  )
}