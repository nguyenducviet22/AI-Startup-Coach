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

export function DocumentWorkspace({ startupId, startupName = "Startup chưa đặt tên", selectedDocType, onSelectDocType, onOpenReport }: DocumentWorkspaceProps) {
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
      showToast(`Đã khôi phục thành phiên bản ${document.version}.`, "success");
    },
    onError: () => showToast("Không thể khôi phục phiên bản. Vui lòng thử lại.", "error")
  });

  async function handleDownload(format: DocumentExportFormat) {
    setDownloading(format);
    try {
      await downloadDocument(startupId, selectedDocType, format);
      showToast(`Đã tải ${selectedLabel} dạng ${format.toUpperCase()}.`, "success");
    } catch {
      showToast("Không thể tải tài liệu. Vui lòng thử lại.", "error");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <section className="workspace-section document-workspace" aria-labelledby="documents-heading" id="documents">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Kho tài liệu</p>
          <h2 id="documents-heading">{selectedLabel}</h2>
          <p className="section-description">Tài liệu được AI Coach cập nhật theo nội dung trao đổi của bạn.</p>
        </div>
        {currentDocumentQuery.data ? (
          <div className="document-actions" aria-label={`Tải ${selectedLabel} của ${startupName}`}>
            <button type="button" className="secondary-button" disabled={downloading !== null} onClick={() => void handleDownload("docx")}>{downloading === "docx" ? "Đang tạo..." : "Tải DOCX"}</button>
            <button type="button" className="primary-button" disabled={downloading !== null} onClick={() => void handleDownload("pdf")}>{downloading === "pdf" ? "Đang tạo..." : "Tải PDF"}</button>
          </div>
        ) : null}
      </div>

      <div className="document-tabs" role="tablist" aria-label="Loại tài liệu">
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
        {onOpenReport ? <button type="button" role="tab" aria-selected="false" className="document-tab" onClick={onOpenReport}>Hồ sơ tổng hợp</button> : null}
      </div>

      {selectedDocType === "funding" && displayedDocument ? <div className="pitch-mode-switch" role="tablist" aria-label="Chế độ xem gọi vốn"><button type="button" role="tab" aria-selected={fundingMode === "content"} className={fundingMode === "content" ? "selected" : ""} onClick={() => setFundingMode("content")}>Nội dung</button><button type="button" role="tab" aria-selected={fundingMode === "presentation"} className={fundingMode === "presentation" ? "selected" : ""} onClick={() => setFundingMode("presentation")}>Trình chiếu</button></div> : null}

      {currentDocumentQuery.isLoading ? (
        <Skeleton lines={5} />
      ) : currentDocumentQuery.error ? (
        <p className="form-error">{currentDocumentQuery.error.message}</p>
      ) : displayedDocument ? (
        selectedDocType === "funding" && fundingMode === "presentation" ? <PitchDeckView startupId={startupId} startupName={startupName} slides={pitchSlides} /> :
        <>
        {previewDocument ? <div className="version-preview-banner"><span>Bạn đang xem phiên bản {previewDocument.version}</span><button type="button" className="text-button" onClick={() => setPreviewDocument(null)}>Quay lại hiện tại</button></div> : null}
        <div className="document-view document-page-preview">
          <header className="document-page-heading">
            <p>{startupName}</p>
            <h3>{selectedLabel}</h3>
          </header>
          <div className="document-meta">
            <span className="status-pill">Phiên bản {displayedDocument.version}</span>
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
        title={pendingRestore ? `Khôi phục phiên bản ${pendingRestore.version}?` : "Khôi phục phiên bản?"}
        description="Nội dung được chọn sẽ được sao chép thành phiên bản mới. Các phiên bản hiện có vẫn được giữ nguyên."
        confirmLabel={restoreMutation.isPending ? "Đang khôi phục..." : "Khôi phục phiên bản"}
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
      <h3>Chưa có {label}</h3>
      <p>Trò chuyện với AI Coach ở giai đoạn tương ứng. Tài liệu sẽ xuất hiện tại đây sau khi có đủ thông tin.</p>
    </div>
  );
}

function readPitchSlides(value: unknown): PitchSlide[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is PitchSlide => item !== null && typeof item === "object");
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Chưa có thời gian";
  }

  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}
