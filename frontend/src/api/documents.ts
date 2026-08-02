import { ApiError, apiRequest, apiUrl } from "./client";

export type DocumentType = "lean_canvas" | "bmc" | "swot" | "product_plan" | "marketing" | "funding";

export type StartupDocument = {
  id: string;
  startup_id: string;
  doc_type: string;
  version: number;
  is_current: boolean | null;
  created_at: string | null;
  content: Record<string, unknown>;
};

export type DocumentHistoryResponse = {
  documents: StartupDocument[];
};

export async function getCurrentDocument(startupId: string, docType: DocumentType): Promise<StartupDocument | null> {
  try {
    return await apiRequest<StartupDocument>(`/startups/${startupId}/documents/${docType}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getDocumentHistory(
  startupId: string,
  docType: DocumentType
): Promise<DocumentHistoryResponse> {
  return apiRequest<DocumentHistoryResponse>(`/startups/${startupId}/documents/${docType}/history`);
}

export function restoreDocumentVersion(startupId: string, docType: DocumentType, version: number): Promise<StartupDocument> {
  return apiRequest<StartupDocument>(`/startups/${startupId}/documents/${docType}/versions/${version}/restore`, {
    method: "POST"
  });
}

export type DocumentExportFormat = "pdf" | "docx";

export async function downloadDocument(
  startupId: string,
  docType: DocumentType,
  format: DocumentExportFormat
): Promise<void> {
  const response = await fetch(apiUrl(`/startups/${startupId}/documents/${docType}/export?format=${format}`), {
    headers: { Accept: format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
  });
  if (!response.ok) {
    throw new Error(`Không thể tải tài liệu (${response.status}).`);
  }
  const blobUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filenameFromDisposition(response.headers.get("Content-Disposition")) ?? `tai-lieu.${format}`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

function filenameFromDisposition(value: string | null): string | null {
  const match = value?.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
}
