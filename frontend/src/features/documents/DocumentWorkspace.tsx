import { useQuery } from "@tanstack/react-query";

import { getCurrentDocument, getDocumentHistory, type DocumentType } from "../../api/documents";
import { DOCUMENT_LABELS, DOCUMENT_TYPES } from "./documentTypes";
import { DocumentLayout } from "./DocumentLayouts";
import { VersionHistory } from "./VersionHistory";

type DocumentWorkspaceProps = {
  startupId: string;
  selectedDocType: DocumentType;
  onSelectDocType: (docType: DocumentType) => void;
};

export function DocumentWorkspace({ startupId, selectedDocType, onSelectDocType }: DocumentWorkspaceProps) {
  const currentDocumentQuery = useQuery({
    queryKey: ["document", startupId, selectedDocType],
    queryFn: () => getCurrentDocument(startupId, selectedDocType),
    enabled: Boolean(startupId)
  });
  const historyQuery = useQuery({
    queryKey: ["document-history", startupId, selectedDocType],
    queryFn: () => getDocumentHistory(startupId, selectedDocType),
    enabled: Boolean(startupId)
  });
  const selectedLabel = DOCUMENT_LABELS[selectedDocType];

  return (
    <section className="workspace-section document-workspace" aria-labelledby="documents-heading" id="documents">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Documents</p>
          <h2 id="documents-heading">{selectedLabel}</h2>
        </div>
      </div>

      <div className="document-tabs" role="tablist" aria-label="Document types">
        {DOCUMENT_TYPES.map((docType) => (
          <button
            type="button"
            role="tab"
            aria-selected={docType === selectedDocType}
            className={docType === selectedDocType ? "document-tab selected" : "document-tab"}
            onClick={() => onSelectDocType(docType)}
            key={docType}
          >
            {DOCUMENT_LABELS[docType]}
          </button>
        ))}
      </div>

      {currentDocumentQuery.isLoading ? (
        <p className="document-muted">Loading document...</p>
      ) : currentDocumentQuery.error ? (
        <p className="form-error">{currentDocumentQuery.error.message}</p>
      ) : currentDocumentQuery.data ? (
        <div className="document-view">
          <div className="document-meta">
            <span className="status-pill">Version {currentDocumentQuery.data.version}</span>
            <span>{formatDate(currentDocumentQuery.data.created_at)}</span>
          </div>
          <DocumentLayout docType={selectedDocType} document={currentDocumentQuery.data} />
        </div>
      ) : (
        <EmptyDocumentState label={selectedLabel} />
      )}

      <VersionHistory
        documents={historyQuery.data?.documents ?? []}
        isLoading={historyQuery.isLoading}
        error={historyQuery.error}
      />
    </section>
  );
}

function EmptyDocumentState({ label }: { label: string }) {
  return (
    <div className="document-empty">
      <h3>No {label} yet</h3>
      <p>Generate this document from the matching coaching stage, then it will appear here with its history.</p>
    </div>
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
