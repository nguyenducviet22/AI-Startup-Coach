import type { ChatMessage, ResearchResponse } from "../../api/chat";
import { Skeleton } from "../../components/Skeleton";
import { ResearchEvidence } from "../research/ResearchEvidence";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MessageListProps = {
  messages: ChatMessage[];
  isLoading: boolean;
  research?: ResearchResponse | null;
};

export function MessageList({ messages, isLoading, research = null }: MessageListProps) {
  if (isLoading) {
    return <Skeleton lines={4} />;
  }

  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <div className="empty-icon" aria-hidden="true">✦</div>
        <h3>Start the conversation</h3>
        <p>Share what you know about your idea. Your Coach will ask questions and help identify the next step.</p>
      </div>
    );
  }

  return (
    <div className="message-list" aria-label="Conversation messages">
      {messages.map((message) => (
        <article className={`chat-message chat-message-${message.role}`} key={message.sequence}>
          <p className="message-role">{message.role === "user" ? "You" : "AI Coach"}</p>
          {message.role === "assistant" ? (
            <div className="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="message-content message-content-plain">{message.content}</p>
          )}
        </article>
      ))}
      {research ? <ResearchEvidence research={research} /> : null}
    </div>
  );
}
