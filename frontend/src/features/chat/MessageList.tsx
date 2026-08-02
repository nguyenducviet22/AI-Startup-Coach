import type { ChatMessage } from "../../api/chat";
import { Skeleton } from "../../components/Skeleton";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MessageListProps = {
  messages: ChatMessage[];
  isLoading: boolean;
};

export function MessageList({ messages, isLoading }: MessageListProps) {
  if (isLoading) {
    return <Skeleton lines={4} />;
  }

  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <div className="empty-icon" aria-hidden="true">✦</div>
        <h3>Bắt đầu cuộc trò chuyện</h3>
        <p>Hãy chia sẻ điều bạn đã biết về ý tưởng. Coach sẽ đặt câu hỏi và giúp bạn xác định bước tiếp theo.</p>
      </div>
    );
  }

  return (
    <div className="message-list" aria-label="Tin nhắn trò chuyện">
      {messages.map((message) => (
        <article className={`chat-message chat-message-${message.role}`} key={message.sequence}>
          <p className="message-role">{message.role === "user" ? "Bạn" : "AI Coach"}</p>
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
