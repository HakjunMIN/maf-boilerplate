interface WebResultsPaneProps {
  results: string[]
}

export function WebResultsPane({ results }: WebResultsPaneProps) {
  return (
    <div className="result-pane">
      <div className="pane-head">
        <h3>Web research results</h3>
      </div>
      <ol className="web-results">
        {results.map((result, index) => (
          <li key={`${index + 1}-${result.slice(0, 24)}`}>{result}</li>
        ))}
      </ol>
    </div>
  )
}