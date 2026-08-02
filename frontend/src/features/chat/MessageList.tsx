import type { ChatMessage } from "../../api/chat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MessageListProps = {
  messages: ChatMessage[];
  isLoading: boolean;
};

export function MessageList({ messages, isLoading }: MessageListProps) {
  if (isLoading) {
    return <p className="sidebar-note">Loading chat history...</p>;
  }

  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <h3>No messages yet</h3>
        <p>Start with what you know. The coach will help shape the next step.</p>
      </div>
    );
  }

  return (
    <div className="message-list" aria-label="Chat messages">
      {messages.map((message) => (
        <article className={`chat-message chat-message-${message.role}`} key={message.sequence}>
          <p className="message-role">{message.role === "user" ? "You" : "Coach"}</p>
          {message.role === "assistant" ? (
            <div className="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="message-content message-content-plain">{message.content}</p>
          )}
        </article>
      ))}
    </div>
  );
}
