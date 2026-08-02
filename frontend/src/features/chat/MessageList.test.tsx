import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageList } from "./MessageList";

describe("MessageList", () => {
  it("renders hydrated messages in the provided sequence order", () => {
    render(
      <MessageList
        isLoading={false}
        messages={[
          { role: "user", content: "First user message", created_at: null, sequence: 1 },
          { role: "assistant", content: "First coach reply", created_at: null, sequence: 2 }
        ]}
      />
    );

    const messages = screen.getAllByRole("article");
    expect(messages[0]).toHaveTextContent("First user message");
    expect(messages[1]).toHaveTextContent("First coach reply");
  });

  it("renders assistant Markdown with list structure and bold labels", () => {
    render(
      <MessageList
        isLoading={false}
        messages={[
          {
            role: "assistant",
            content: "1. **Origin**\n\n2. **Problem**\n\nFinal question?",
            created_at: null,
            sequence: 1
          }
        ]}
      />
    );

    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Origin").tagName).toBe("STRONG");
    expect(screen.getByText("Problem").tagName).toBe("STRONG");
    expect(screen.getByText("Final question?")).toBeInTheDocument();
  });

  it("keeps plain-text user messages and does not render raw HTML", () => {
    render(
      <MessageList
        isLoading={false}
        messages={[
          {
            role: "user",
            content: "Line one\nLine two",
            created_at: null,
            sequence: 1
          },
          {
            role: "assistant",
            content: "<img src=x onerror=alert(1)>Safe text",
            created_at: null,
            sequence: 2
          }
        ]}
      />
    );

    expect(screen.getByText(/Line one/)).toHaveClass("message-content-plain");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getAllByRole("article")[1]).toHaveTextContent("Safe text");
    expect(screen.getAllByRole("article")[1]).toHaveTextContent("<img src=x onerror=alert(1)>");
  });
});
