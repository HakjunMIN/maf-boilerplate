import { useState } from 'react'

import type { AppConfig } from '../hooks/useConfig'

interface ConfigPanelProps {
  config: AppConfig
  onChange: (updater: AppConfig | ((current: AppConfig) => AppConfig)) => void
}

export function ConfigPanel({ config, onChange }: ConfigPanelProps) {
  const [showToken, setShowToken] = useState(false)

  return (
    <section className="panel panel--config">
      <div className="section-head">
        <div>
          <p className="section-kicker">Connection</p>
          <h2>Backend configuration</h2>
        </div>
        <p className="section-meta">Saved in localStorage. Leave base URL blank to use the Vite proxy or same-origin deployment.</p>
      </div>

      <div className="config-grid">
        <label className="field">
          <span className="field__label">API base URL</span>
          <input
            className="field__input"
            type="text"
            value={config.baseUrl}
            placeholder="Blank = same origin / proxy"
            onChange={(event) => {
              const value = event.target.value
              onChange((current) => ({ ...current, baseUrl: value }))
            }}
          />
        </label>

        <label className="field field--token">
          <span className="field__label">Bearer token</span>
          <div className="field__token-wrap">
            <input
              className="field__input"
              type={showToken ? 'text' : 'password'}
              value={config.token}
              placeholder="API_BEARER_TOKEN"
              onChange={(event) => {
                const value = event.target.value
                onChange((current) => ({ ...current, token: value }))
              }}
            />
            <button
              className="ghost-button ghost-button--small"
              type="button"
              onClick={() => setShowToken((current) => !current)}
            >
              {showToken ? 'Hide' : 'Show'}
            </button>
          </div>
        </label>
      </div>
    </section>
  )
}