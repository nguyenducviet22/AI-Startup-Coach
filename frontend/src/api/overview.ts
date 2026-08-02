import { apiRequest } from "./client";
import type { DocumentType } from "./documents";
import type { StageName } from "./startups";

export type StartupOverview = {
  current_stage: StageName;
  journey_completed_steps: number;
  journey_total_steps: number;
  completed_documents: number;
  total_documents: number;
  total_versions: number;
  documents: { doc_type: DocumentType; exists: boolean; version: number | null; updated_at: string | null }[];
  recent_updates: { doc_type: DocumentType; version: number; updated_at: string | null }[];
};

export function getStartupOverview(startupId: string): Promise<StartupOverview> {
  return apiRequest<StartupOverview>(`/startups/${startupId}/overview`);
}
