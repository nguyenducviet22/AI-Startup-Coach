import { apiRequest, getStoredOpenRouterApiKey } from "./client";

export type ChatRole = "user" | "assistant";

export type StageReadiness = {
  ready: boolean;
  missing_fields: string[];
};

export type ChatMessage = {
  role: ChatRole;
  content: string;
  created_at: string | null;
  sequence: number;
};

export type ChatMessagesResponse = {
  session_id: string | null;
  messages: ChatMessage[];
};

export type ChatResponse = {
  session_id: string;
  message: string;
  stage_readiness: StageReadiness | null;
  research?: ResearchResponse | null;
};

export type ResearchEvidence = { source_id: string; url: string; title: string; excerpt: string; retrieved_at: string; published_at: string | null; authority: string; legal_or_regulatory: boolean };
export type ResearchResponse = { evidence: ResearchEvidence[]; cache_hit: boolean; retrieved_at: string; served_at: string; legal_notice: string | null };

export async function getChatMessages(
  startupId: string,
  sessionId: string | null,
  limit = 50,
  beforeSequence?: number
): Promise<ChatMessagesResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  if (beforeSequence !== undefined) {
    params.set("before_sequence", String(beforeSequence));
  }
  return apiRequest<ChatMessagesResponse>(`/startups/${startupId}/chat/messages?${params.toString()}`);
}

export async function sendChatMessage(
  startupId: string,
  message: string,
  sessionId: string | null
): Promise<ChatResponse> {
  const apiKey = getStoredOpenRouterApiKey();
  return apiRequest<ChatResponse>(`/startups/${startupId}/chat`, {
    method: "POST",
    headers: apiKey ? { "X-OpenRouter-Api-Key": apiKey } : undefined,
    body: JSON.stringify({
      message,
      session_id: sessionId
    })
  });
}
