import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getChatMessages,
  sendChatMessage,
  type StageReadiness
} from "../../api/chat";
import type { StageName } from "../../api/startups";
import { useChatSessionStore } from "../../stores/chatSessionStore";
import { useWorkspacePreferencesStore } from "../../stores/workspacePreferencesStore";
import { MessageList } from "./MessageList";
import { StageReadinessPrompt } from "./StageReadinessPrompt";
import { useToastStore } from "../../stores/toastStore";

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
  const draft = useWorkspacePreferencesStore((state) => state.workspaces[startupId]?.chatDraft ?? "");
  const updateWorkspace = useWorkspacePreferencesStore((state) => state.updateWorkspace);
  const [readiness, setReadiness] = useState<StageReadiness | null>(null);
  const showToast = useToastStore((state) => state.showToast);
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
      void queryClient.invalidateQueries({ queryKey: ["document", startupId] });
      void queryClient.invalidateQueries({ queryKey: ["document-history", startupId] });
      void queryClient.invalidateQueries({ queryKey: ["startup-overview", startupId] });
      void queryClient.invalidateQueries({ queryKey: ["startup-report", startupId] });
      updateWorkspace(startupId, { chatDraft: "" });
    },
    onError: () => showToast("Không thể gửi tin nhắn. Vui lòng thử lại.", "error")
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
          <p className="eyebrow">AI Coach</p>
          <h2 id="chat-heading">{isCompleted ? "Lịch sử coaching" : "Trò chuyện cùng Coach"}</h2>
          <p className="section-description">Trao đổi tự nhiên; Coach sẽ tổng hợp thông tin vào tài liệu của bạn.</p>
        </div>
        {!isCompleted && currentDocumentLabel && onOpenCurrentDocument ? (
          <button type="button" className="secondary-button" onClick={onOpenCurrentDocument}>
            Mở {currentDocumentLabel}
          </button>
        ) : null}
      </div>

      <MessageList messages={messages} isLoading={historyQuery.isLoading} />

      {isCompleted ? (
        <div className="completion-summary">
          <h3>Hành trình coaching đã hoàn thành</h3>
          <p>Lịch sử trò chuyện vẫn được lưu tại đây. Bạn có thể xem lại và hoàn thiện các tài liệu đã tạo.</p>
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
              Tin nhắn
              <textarea
                value={draft}
                onChange={(event) => updateWorkspace(startupId, { chatDraft: event.target.value })}
                rows={4}
                placeholder="Chia sẻ điều bạn đã biết, câu hỏi hoặc giả định cần kiểm chứng..."
              />
            </label>
            {sendMutation.error ? <p className="form-error">{sendMutation.error.message}</p> : null}
            <button type="submit" className="primary-button" disabled={!draft.trim() || sendMutation.isPending}>
              {sendMutation.isPending ? "Đang gửi..." : "Gửi tin nhắn"}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
