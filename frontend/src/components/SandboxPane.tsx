import type { SandboxResultResponse } from '../types/api'

interface SandboxPaneProps {
  result: SandboxResultResponse
}

export function SandboxPane({ result }: SandboxPaneProps) {
  return (
    <div className="result-pane">
      <div className="pane-head">
        <h3>Sandbox execution</h3>
        <span className={`status-pill status-pill--${result.exit_code === 0 ? 'completed' : 'failed'}`}>
          exit {result.exit_code}
        </span>
      </div>

      <div className="terminal-grid">
        <div>
          <p className="terminal-label">stdout</p>
          <pre className="terminal-block">{result.stdout || 'No stdout'}</pre>
        </div>
        <div>
          <p className="terminal-label">stderr</p>
          <pre className="terminal-block">{result.stderr || 'No stderr'}</pre>
        </div>
      </div>

      {result.artifacts.length > 0 ? (
        <div className="artifact-block">
          <p className="terminal-label">artifacts</p>
          <ul className="artifact-list">
            {result.artifacts.map((artifact) => <li key={artifact}>{artifact}</li>)}
          </ul>
        </div>
      ) : null}
    </div>
  )
}