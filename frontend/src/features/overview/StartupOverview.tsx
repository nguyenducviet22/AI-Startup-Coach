import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getStartupOverview } from "../../api/overview";
import type { StageName } from "../../api/startups";
import { Skeleton } from "../../components/Skeleton";
import { DOCUMENT_LABELS } from "../documents/documentTypes";
import { STAGE_LABELS } from "../stages/stageLabels";

export function StartupOverview({ startupId, currentStage, onContinue }: { startupId: string; currentStage: StageName; onContinue: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const query = useQuery({ queryKey: ["startup-overview", startupId], queryFn: () => getStartupOverview(startupId), enabled: Boolean(startupId) });
  if (query.isLoading) return <section className="startup-overview"><Skeleton lines={2} compact /></section>;
  if (query.error) return <section className="startup-overview overview-error"><p className="form-error">Unable to load the startup overview.</p><button type="button" className="text-button" onClick={() => void query.refetch()}>Try again</button></section>;
  const overview = query.data;
  if (!overview) return null;
  const percent = Math.round((overview.journey_completed_steps / overview.journey_total_steps) * 100);
  return <section className="startup-overview" aria-labelledby="startup-overview-heading">
    <div className="startup-overview-summary">
      <div><p className="eyebrow">Startup progress</p><h2 id="startup-overview-heading">{overview.journey_completed_steps}/{overview.journey_total_steps} stages · {overview.completed_documents}/{overview.total_documents} documents · {overview.total_versions} versions</h2></div>
      <div className="startup-overview-actions"><button type="button" className="text-button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? "Collapse" : "Details"}</button><button type="button" className="secondary-button compact-button" onClick={onContinue}>Continue to {STAGE_LABELS[currentStage]}</button></div>
    </div>
    <div className="progress-track" aria-label={`${percent}% complete`}><span style={{ width: `${percent}%` }} /></div>
    {expanded ? <div className="startup-overview-details">
      <div><h3>Documents</h3><ul className="overview-document-list">{overview.documents.map((document) => <li key={document.doc_type}><span aria-hidden="true">{document.exists ? "✓" : "○"}</span><span>{DOCUMENT_LABELS[document.doc_type]}</span><small>{document.version ? `Version ${document.version}` : "Not created"}</small></li>)}</ul></div>
      <div><h3>Recent updates</h3>{overview.recent_updates.length ? <ol className="overview-recent-list">{overview.recent_updates.map((item, index) => <li key={`${item.doc_type}-${item.version}-${index}`}><strong>{DOCUMENT_LABELS[item.doc_type]}</strong><span>Version {item.version} · {formatDate(item.updated_at)}</span></li>)}</ol> : <p className="document-muted">No document updates yet.</p>}</div>
    </div> : null}
  </section>;
}

function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "No timestamp";
}
