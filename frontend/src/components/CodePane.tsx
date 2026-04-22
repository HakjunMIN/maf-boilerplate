import { useState } from 'react'

interface CodePaneProps {
  code: string
}

export function CodePane({ code }: CodePaneProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="result-pane">
      <div className="pane-head">
        <h3>Generated code</h3>
        <button className="ghost-button ghost-button--small" type="button" onClick={() => void handleCopy()}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="code-block"><code>{code}</code></pre>
    </div>
  )
}