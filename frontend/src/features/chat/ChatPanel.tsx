import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getChatMessages,
  sendChatMessage,
  type StageReadiness
} from "../../api/chat";
import type { StageName } from "../../api/startups";
import { useChatSessionStore } from "../../stores/chatSessionStore";
import { MessageList } from "./MessageList";
import { StageReadinessPrompt } from "./StageReadinessPrompt";

type ChatPanelProps = {
  startupId: string;
  currentStage: StageName;
  isAdvancing?: boolean;
  onAdvanceStage: () => void;
  currentDocumentLabel?: string | null;
  onOpenCurrentDocument?: () => void;
};

export function ChatPanel({
  startupId,
  currentStage,
  isAdvancing = false,
  onAdvanceStage,
  currentDocumentLabel = null,
  onOpenCurrentDocument
}: ChatPanelProps) {
  const getSessionId = useChatSessionStore((state) => state.getSessionId);
  const setSessionId = useChatSessionStore((state) => state.setSessionId);
  const queryClient = useQueryClient();
  const sessionId = getSessionId(startupId);
  const [draft, setDraft] = useState("");
  const [readiness, setReadiness] = useState<StageReadiness | null>(null);
  const isCompleted = currentStage === "completed";

  const historyQuery = useQuery({
    queryKey: ["chat-messages", startupId, sessionId],
    queryFn: () => getChatMessages(startupId, sessionId),
    enabled: Boolean(startupId),
    staleTime: 15_000
  });

  const messages = useMemo(() => historyQuery.data?.messages ?? [], [historyQuery.data?.messages]);

  const sendMutation = useMutation({
    mutationFn: (message: string) => sendChatMessage(startupId, message, sessionId),
    onSuccess(response) {
      setSessionId(startupId, response.session_id);
      setReadiness(response.stage_readiness);
      void queryClient.invalidateQueries({ queryKey: ["chat-messages", startupId, response.session_id] });
      setDraft("");
    }
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isCompleted) {
      return;
    }
    sendMutation.mutate(message);
  }

  return (
    <section className="workspace-section chat-panel" aria-labelledby="chat-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Coach</p>
          <h2 id="chat-heading">{isCompleted ? "Coaching archive" : "Chat"}</h2>
        </div>
        {!isCompleted && currentDocumentLabel && onOpenCurrentDocument ? (
          <button type="button" className="secondary-button" onClick={onOpenCurrentDocument}>
            Open {currentDocumentLabel}
          </button>
        ) : null}
      </div>

      <MessageList messages={messages} isLoading={historyQuery.isLoading} />

      {isCompleted ? (
        <div className="completion-summary">
          <h3>Guided coaching is complete</h3>
          <p>Chat history stays available here. Use the document views to review and refine generated work.</p>
        </div>
      ) : (
        <>
          <StageReadinessPrompt
            readiness={readiness}
            currentStage={currentStage}
            isAdvancing={isAdvancing}
            onAdvanceStage={onAdvanceStage}
          />

          <form className="message-composer" onSubmit={handleSubmit}>
            <label>
              Message
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                rows={4}
                placeholder="Tell the coach what you know so far..."
              />
            </label>
            {sendMutation.error ? <p className="form-error">{sendMutation.error.message}</p> : null}
            <button type="submit" className="primary-button" disabled={!draft.trim() || sendMutation.isPending}>
              {sendMutation.isPending ? "Sending..." : "Send"}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
