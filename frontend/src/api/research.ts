import { apiRequest } from "./client";
import type { ResearchResponse } from "./chat";

export type FounderResearchRequest = {
  query?: string;
  urls?: string[];
  category?: "general" | "news" | "pricing" | "legal";
  jurisdiction?: string;
  force_refresh?: boolean;
  max_results?: number;
  session_id?: string | null;
};

export function runResearch(startupId: string, request: FounderResearchRequest): Promise<ResearchResponse> {
  return apiRequest<ResearchResponse>(`/startups/${startupId}/research`, { method: "POST", body: JSON.stringify(request) });
}
