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
});
