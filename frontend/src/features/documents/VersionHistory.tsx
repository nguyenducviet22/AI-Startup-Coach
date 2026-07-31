import type { StartupDocument } from "../../api/documents";

type VersionHistoryProps = {
  documents: StartupDocument[];
  isLoading: boolean;
  error: Error | null;
};

export function VersionHistory({ documents, isLoading, error }: VersionHistoryProps) {
  if (isLoading) {
    return <p className="document-muted">Loading version history...</p>;
  }

  if (error) {
    return <p className="form-error">{error.message}</p>;
  }

  if (documents.length === 0) {
    return <p className="document-muted">No versions yet.</p>;
  }

  return (
    <section className="version-history" aria-labelledby="version-history-heading">
      <h3 id="version-history-heading">Version History</h3>
      <ol>
        {documents.map((document) => (
          <li key={document.id}>
            <span>
              Version {document.version}
              {document.is_current ? " current" : ""}
            </span>
            <time dateTime={document.created_at ?? undefined}>{formatDate(document.created_at)}</time>
          </li>
        ))}
      </ol>
    </section>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}
