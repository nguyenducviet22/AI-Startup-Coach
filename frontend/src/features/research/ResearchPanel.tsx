import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import { runResearch, type FounderResearchRequest } from "../../api/research";
import { ResearchEvidence } from "./ResearchEvidence";

type ResearchPanelProps = {
  startupId: string;
  sessionId: string | null;
};

const CATEGORIES: Array<NonNullable<FounderResearchRequest["category"]>> = ["general", "news", "pricing", "legal"];

function urlsFromInput(value: string): string[] {
  return value.split(/\r?\n/).map((url) => url.trim()).filter(Boolean);
}

function errorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 429) {
    return "Research rate limit reached. Please wait a moment before trying again.";
  }
  return error.message || "Unable to complete research. Please try again.";
}

export function ResearchPanel({ startupId, sessionId }: ResearchPanelProps) {
  const [query, setQuery] = useState("");
  const [urls, setUrls] = useState("");
  const [category, setCategory] = useState<NonNullable<FounderResearchRequest["category"]>>("general");
  const [jurisdiction, setJurisdiction] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const researchMutation = useMutation({
    mutationFn: (request: FounderResearchRequest) => runResearch(startupId, request)
  });

  function startResearch(forceRefresh = false) {
    const trimmedQuery = query.trim();
    const parsedUrls = urlsFromInput(urls);
    if (!trimmedQuery && parsedUrls.length === 0) {
      setValidationError("Enter a research question or at least one URL.");
      return;
    }
    if (category === "legal" && !jurisdiction.trim()) {
      setValidationError("Jurisdiction is required for legal research.");
      return;
    }
    setValidationError(null);
    researchMutation.mutate({
      query: trimmedQuery || undefined,
      urls: parsedUrls.length > 0 ? parsedUrls : undefined,
      category,
      jurisdiction: jurisdiction.trim() || undefined,
      session_id: sessionId,
      force_refresh: forceRefresh
    });
  }

  return (
    <section className="workspace-section research-panel" aria-labelledby="research-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Founder research</p>
          <h2 id="research-heading">Research the evidence</h2>
          <p className="section-description">Search a question or extract evidence from a source URL.</p>
        </div>
      </div>
      <form className="research-form" onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); startResearch(); }}>
        <label>
          Research question
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={3} placeholder="What do you want to validate?" />
        </label>
        <label>
          Source URLs
          <textarea value={urls} onChange={(event) => setUrls(event.target.value)} rows={3} placeholder="One https:// URL per line" />
        </label>
        <label>
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value as NonNullable<FounderResearchRequest["category"]>)}>
            {CATEGORIES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>
          Jurisdiction {category === "legal" ? "(required)" : "(optional)"}
          <input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} placeholder="For example, Vietnam" />
        </label>
        {validationError ? <p className="form-error" role="alert">{validationError}</p> : null}
        {researchMutation.error ? <p className="form-error" role="alert">{errorMessage(researchMutation.error)}</p> : null}
        <div className="research-actions">
          <button type="submit" className="primary-button" disabled={researchMutation.isPending}>
            {researchMutation.isPending ? "Researching..." : "Run research"}
          </button>
          {researchMutation.data ? (
            <button type="button" className="secondary-button" disabled={researchMutation.isPending} onClick={() => startResearch(true)}>
              Refresh evidence
            </button>
          ) : null}
          {researchMutation.error ? (
            <button type="button" className="secondary-button" disabled={researchMutation.isPending} onClick={() => researchMutation.reset()}>
              Retry
            </button>
          ) : null}
        </div>
      </form>
      {researchMutation.data ? <ResearchEvidence research={researchMutation.data} /> : null}
    </section>
  );
}
