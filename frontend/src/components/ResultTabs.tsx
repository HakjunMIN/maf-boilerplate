import { useEffect, useMemo, useState } from 'react'

import type { JobResponse } from '../types/api'
import { CodePane } from './CodePane'
import { SandboxPane } from './SandboxPane'
import { WebResultsPane } from './WebResultsPane'

type TabKey = 'summary' | 'code' | 'sandbox' | 'web'

interface ResultTabsProps {
  job: JobResponse
}

export function ResultTabs({ job }: ResultTabsProps) {
  const tabs = useMemo(() => {
    const nextTabs: Array<{ key: TabKey; label: string }> = [{ key: 'summary', label: 'Summary' }]
    if (job.generated_code.trim()) {
      nextTabs.push({ key: 'code', label: 'Code' })
    }
    if (job.sandbox_result) {
      nextTabs.push({ key: 'sandbox', label: 'Sandbox' })
    }
    if (job.web_search_results.length > 0) {
      nextTabs.push({ key: 'web', label: 'Web' })
    }
    return nextTabs
  }, [job.generated_code, job.sandbox_result, job.web_search_results])

  const [activeTab, setActiveTab] = useState<TabKey>('summary')

  useEffect(() => {
    if (!tabs.some((tab) => tab.key === activeTab)) {
      setActiveTab('summary')
    }
  }, [activeTab, tabs])

  return (
    <div className="tabs-shell">
      <div className="tab-row" role="tablist" aria-label="Job result views">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab-button ${tab.key === activeTab ? 'tab-button--active' : ''}`}
            type="button"
            role="tab"
            aria-selected={tab.key === activeTab}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'summary' ? (
        <div className="result-pane">
          <div className="pane-head">
            <h3>Summary</h3>
          </div>
          <div className="summary-block">
            {job.summary ? <p>{job.summary}</p> : <p className="summary-empty">Waiting for summary output.</p>}
            {job.error_message ? <p className="error-text">{job.error_message}</p> : null}
          </div>
        </div>
      ) : null}

      {activeTab === 'code' && job.generated_code.trim() ? <CodePane code={job.generated_code} /> : null}
      {activeTab === 'sandbox' && job.sandbox_result ? <SandboxPane result={job.sandbox_result} /> : null}
      {activeTab === 'web' && job.web_search_results.length > 0 ? <WebResultsPane results={job.web_search_results} /> : null}
    </div>
  )
}