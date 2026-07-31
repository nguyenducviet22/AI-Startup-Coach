import { apiRequest } from "./client";

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
};

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
  return apiRequest<ChatResponse>(`/startups/${startupId}/chat`, {
    method: "POST",
    body: JSON.stringify({
      message,
      session_id: sessionId
    })
  });
}
