import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { downloadDocument, getCurrentDocument, getDocumentHistory, restoreDocumentVersion, type DocumentExportFormat, type DocumentType, type StartupDocument } from "../../api/documents";
import { DOCUMENT_LABELS, DOCUMENT_TYPES } from "./documentTypes";
import { DocumentLayout } from "./DocumentLayouts";
import { VersionHistory } from "./VersionHistory";
import { Skeleton } from "../../components/Skeleton";
import { useToastStore } from "../../stores/toastStore";
import { useEffect, useState } from "react";
import { ConfirmationDialog } from "../../components/ConfirmationDialog";
import { VersionCompare } from "./VersionCompare";
import { PitchDeckView, type PitchSlide } from "../pitch/PitchDeckView";

type DocumentWorkspaceProps = {
  startupId: string;
  startupName?: string;
  selectedDocType: DocumentType;
  onSelectDocType: (docType: DocumentType) => void;
  onOpenReport?: () => void;
};

export function DocumentWorkspace({ startupId, startupName = "Unnamed startup", selectedDocType, onSelectDocType, onOpenReport }: DocumentWorkspaceProps) {
  const [downloading, setDownloading] = useState<DocumentExportFormat | null>(null);
  const [previewDocument, setPreviewDocument] = useState<StartupDocument | null>(null);
  const [compareDocument, setCompareDocument] = useState<StartupDocument | null>(null);
  const [pendingRestore, setPendingRestore] = useState<StartupDocument | null>(null);
  const [fundingMode, setFundingMode] = useState<"content" | "presentation">("content");
  const showToast = useToastStore((state) => state.showToast);
  const queryClient = useQueryClient();
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
  const displayedDocument = previewDocument ?? currentDocumentQuery.data;
  const pitchSlides = readPitchSlides(displayedDocument?.content.pitch_outline);
  useEffect(() => {
    setFundingMode("content");
    setPreviewDocument(null);
    setCompareDocument(null);
    setPendingRestore(null);
  }, [selectedDocType]);
  const restoreMutation = useMutation({
    mutationFn: (document: StartupDocument) => restoreDocumentVersion(startupId, selectedDocType, document.version),
    onSuccess(document) {
      setPreviewDocument(null);
      setCompareDocument(null);
      setPendingRestore(null);
      queryClient.setQueryData(["document", startupId, selectedDocType], document);
      void queryClient.invalidateQueries({ queryKey: ["document-history", startupId, selectedDocType] });
      void queryClient.invalidateQueries({ queryKey: ["startup-overview", startupId] });
      void queryClient.invalidateQueries({ queryKey: ["startup-report", startupId] });
      showToast(`Restored version ${document.version}.`, "success");
    },
    onError: () => showToast("Unable to restore the version. Please try again.", "error")
  });

  async function handleDownload(format: DocumentExportFormat) {
    setDownloading(format);
    try {
      await downloadDocument(startupId, selectedDocType, format);
      showToast(`${selectedLabel} downloaded as ${format.toUpperCase()}.`, "success");
    } catch {
      showToast("Unable to download the document. Please try again.", "error");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <section className="workspace-section document-workspace" aria-labelledby="documents-heading" id="documents">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Document workspace</p>
          <h2 id="documents-heading">{selectedLabel}</h2>
          <p className="section-description">AI Coach updates documents based on your conversation.</p>
        </div>
        {currentDocumentQuery.data ? (
          <div className="document-actions" aria-label={`Download ${selectedLabel} for ${startupName}`}>
            <button type="button" className="secondary-button" disabled={downloading !== null} onClick={() => void handleDownload("docx")}>{downloading === "docx" ? "Creating..." : "Download DOCX"}</button>
            <button type="button" className="primary-button" disabled={downloading !== null} onClick={() => void handleDownload("pdf")}>{downloading === "pdf" ? "Creating..." : "Download PDF"}</button>
          </div>
        ) : null}
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
        {onOpenReport ? <button type="button" role="tab" aria-selected="false" className="document-tab" onClick={onOpenReport}>Startup report</button> : null}
      </div>

      {selectedDocType === "funding" && displayedDocument ? <div className="pitch-mode-switch" role="tablist" aria-label="Funding view mode"><button type="button" role="tab" aria-selected={fundingMode === "content"} className={fundingMode === "content" ? "selected" : ""} onClick={() => setFundingMode("content")}>Content</button><button type="button" role="tab" aria-selected={fundingMode === "presentation"} className={fundingMode === "presentation" ? "selected" : ""} onClick={() => setFundingMode("presentation")}>Presentation</button></div> : null}

      {currentDocumentQuery.isLoading ? (
        <Skeleton lines={5} />
      ) : currentDocumentQuery.error ? (
        <p className="form-error">{currentDocumentQuery.error.message}</p>
      ) : displayedDocument ? (
        selectedDocType === "funding" && fundingMode === "presentation" ? <PitchDeckView startupId={startupId} startupName={startupName} slides={pitchSlides} /> :
        <>
        {previewDocument ? <div className="version-preview-banner"><span>You are viewing version {previewDocument.version}</span><button type="button" className="text-button" onClick={() => setPreviewDocument(null)}>Back to current</button></div> : null}
        <div className="document-view document-page-preview">
          <header className="document-page-heading">
            <p>{startupName}</p>
            <h3>{selectedLabel}</h3>
          </header>
          <div className="document-meta">
            <span className="status-pill">Version {displayedDocument.version}</span>
            <span>{formatDate(displayedDocument.created_at)}</span>
          </div>
          <DocumentLayout docType={selectedDocType} document={displayedDocument} />
        </div>
        </>
      ) : (
        <EmptyDocumentState label={selectedLabel} />
      )}

      <VersionHistory
        documents={historyQuery.data?.documents ?? []}
        isLoading={historyQuery.isLoading}
        error={historyQuery.error}
        onPreview={(document) => { setPreviewDocument(document); setCompareDocument(null); }}
        onCompare={setCompareDocument}
        onRestore={setPendingRestore}
      />
      {compareDocument && currentDocumentQuery.data ? <VersionCompare older={compareDocument} current={currentDocumentQuery.data} onClose={() => setCompareDocument(null)} /> : null}
      <ConfirmationDialog
        open={pendingRestore !== null}
        title={pendingRestore ? `Restore version ${pendingRestore.version}?` : "Restore version?"}
        description="The selected content will be copied into a new version. Existing versions will be preserved."
        confirmLabel={restoreMutation.isPending ? "Restoring..." : "Restore version"}
        onConfirm={() => { if (pendingRestore && !restoreMutation.isPending) restoreMutation.mutate(pendingRestore); }}
        onCancel={() => { if (!restoreMutation.isPending) setPendingRestore(null); }}
      />
    </section>
  );
}

function EmptyDocumentState({ label }: { label: string }) {
  return (
    <div className="document-empty">
      <div className="empty-icon" aria-hidden="true">▤</div>
      <h3>No {label} yet</h3>
      <p>Chat with AI Coach during the corresponding stage. The document will appear once enough information is available.</p>
    </div>
  );
}

function readPitchSlides(value: unknown): PitchSlide[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is PitchSlide => item !== null && typeof item === "object");
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
