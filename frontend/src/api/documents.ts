import { ApiError, apiRequest } from "./client";

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
