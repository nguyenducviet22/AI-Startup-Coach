import type { StartupDocument } from "../../api/documents";
import { Skeleton } from "../../components/Skeleton";

type VersionHistoryProps = {
  documents: StartupDocument[];
  isLoading: boolean;
  error: Error | null;
  onPreview?: (document: StartupDocument) => void;
  onCompare?: (document: StartupDocument) => void;
  onRestore?: (document: StartupDocument) => void;
};

export function VersionHistory({ documents, isLoading, error, onPreview, onCompare, onRestore }: VersionHistoryProps) {
  if (isLoading) {
    return <Skeleton lines={2} compact />;
  }

  if (error) {
    return <p className="form-error">{error.message}</p>;
  }

  if (documents.length === 0) {
    return <p className="document-muted">No previous versions.</p>;
  }

  return (
    <section className="version-history" aria-labelledby="version-history-heading">
      <h3 id="version-history-heading">Version history</h3>
      <ol>
        {documents.map((document) => (
          <li key={document.id}>
            <div className="version-history-copy"><span>
              Version {document.version}
              {document.is_current ? " · current" : ""}
            </span>
            <time dateTime={document.created_at ?? undefined}>{formatDate(document.created_at)}</time>
            </div>
            {!document.is_current ? <div className="version-history-actions">
              {onPreview ? <button type="button" className="text-button" aria-label={`Preview version ${document.version}`} onClick={() => onPreview(document)}>Preview</button> : null}
              {onCompare ? <button type="button" className="text-button" aria-label={`Compare version ${document.version}`} onClick={() => onCompare(document)}>Compare</button> : null}
              {onRestore ? <button type="button" className="text-button" aria-label={`Restore version ${document.version}`} onClick={() => onRestore(document)}>Restore</button> : null}
            </div> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "No timestamp";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}
