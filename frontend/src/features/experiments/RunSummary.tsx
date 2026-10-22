export interface ResearchSummary {
  observations: string[]
  limitations: string[]
}

export function RunSummary({ summary }: { summary: ResearchSummary }) {
  return (
    <section className="run-summary" aria-labelledby="research-summary-title">
      <h3 id="research-summary-title">Research narration</h3>
      {summary.observations.length > 0 && <ul>{summary.observations.map((observation) => <li key={observation}>{observation}</li>)}</ul>}
      <h4>Limitations and uncertainty</h4>
      <ul>{summary.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
    </section>
  )
}
