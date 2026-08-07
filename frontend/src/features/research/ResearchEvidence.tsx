import type { ResearchResponse } from "../../api/chat";

export function ResearchEvidence({ research }: { research: ResearchResponse }) {
  return (
    <section className="research-evidence" aria-label="Research evidence">
      <header className="research-evidence-heading">
        <h3>Research evidence</h3>
        {research.cache_hit ? <span>Cached result</span> : null}
      </header>
      <ul>
        {research.evidence.map((item) => (
          <li key={item.source_id}>
            <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
            <p>Retrieved {item.retrieved_at}{item.published_at ? ` · Published ${item.published_at}` : ""}</p>
            <p>{item.excerpt}</p>
            <p>{item.authority}</p>
          </li>
        ))}
      </ul>
      {research.legal_notice ? <p role="note">{research.legal_notice}</p> : null}
    </section>
  );
}
