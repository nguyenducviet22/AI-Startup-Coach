import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAuthTokens } from "../../api/client";
import { useChatSessionStore } from "../../stores/chatSessionStore";
import { useWorkspacePreferencesStore } from "../../stores/workspacePreferencesStore";
import { ChatPanel } from "./ChatPanel";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("ChatPanel", () => {
  beforeEach(() => {
    clearAuthTokens();
    window.localStorage.clear();
    useChatSessionStore.setState({ sessionIdsByStartup: {} });
    useWorkspacePreferencesStore.setState({ lastStartupId: null, workspaces: {} });
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    clearAuthTokens();
    useChatSessionStore.setState({ sessionIdsByStartup: {} });
    useWorkspacePreferencesStore.setState({ lastStartupId: null, workspaces: {} });
    vi.unstubAllGlobals();
  });

  it("restores a draft per startup and clears it after a successful send", async () => {
    const user = userEvent.setup();
    useWorkspacePreferencesStore.getState().updateWorkspace("startup-1", { chatDraft: "Saved draft" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ session_id: null, messages: [] }))
      .mockResolvedValueOnce(jsonResponse({ session_id: "session-1", message: "Reply", stage_readiness: null }))
      .mockResolvedValueOnce(jsonResponse({
        session_id: "session-1",
        messages: [
          { role: "user", content: "Saved draft", created_at: null, sequence: 1 },
          { role: "assistant", content: "Reply", created_at: null, sequence: 2 }
        ]
      }));

    renderWithQueryClient(
      <ChatPanel startupId="startup-1" currentStage="idea" onAdvanceStage={vi.fn()} />
    );

    expect(await screen.findByLabelText("Tin nhắn")).toHaveValue("Saved draft");
    await user.click(screen.getByRole("button", { name: "Gửi tin nhắn" }));
    await waitFor(() => expect(useWorkspacePreferencesStore.getState().getWorkspace("startup-1").chatDraft).toBe(""));
  });

  it("hydrates history from the chat messages endpoint", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        session_id: "session-1",
        messages: [
          { role: "user", content: "Existing question", created_at: null, sequence: 1 },
          { role: "assistant", content: "Existing answer", created_at: null, sequence: 2 }
        ]
      })
    );

    renderWithQueryClient(
      <ChatPanel startupId="startup-1" currentStage="idea" onAdvanceStage={vi.fn()} />
    );

    expect(await screen.findByText("Existing question")).toBeInTheDocument();
    expect(screen.getByText("Existing answer")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/startups/startup-1/chat/messages?limit=50",
      expect.any(Object)
    );
  });

  it("shows a completion archive instead of an active composer for completed startups", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        session_id: null,
        messages: []
      })
    );

    renderWithQueryClient(
      <ChatPanel startupId="startup-1" currentStage="completed" onAdvanceStage={vi.fn()} />
    );

    expect(await screen.findByText("Hành trình coaching đã hoàn thành")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gửi tin nhắn" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tin nhắn")).not.toBeInTheDocument();
  });

  it("does not duplicate first-send temporary messages when the new session history refetches", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: null,
          messages: []
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: "session-1",
          message: "Let us shape the idea.",
          stage_readiness: null
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: "session-1",
          messages: [
            { role: "user", content: "I want to build this.", created_at: null, sequence: 1 },
            { role: "assistant", content: "Let us shape the idea.", created_at: null, sequence: 2 }
          ]
        })
      );

    renderWithQueryClient(
      <ChatPanel startupId="startup-1" currentStage="idea" onAdvanceStage={vi.fn()} />
    );

    await screen.findByText("Bắt đầu cuộc trò chuyện");
    await user.type(screen.getByLabelText("Tin nhắn"), "I want to build this.");
    await user.click(screen.getByRole("button", { name: "Gửi tin nhắn" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));

    expect(screen.getAllByText("I want to build this.")).toHaveLength(1);
    expect(screen.getAllByText("Let us shape the idea.")).toHaveLength(1);
    expect(fetch).toHaveBeenLastCalledWith(
      "/startups/startup-1/chat/messages?limit=50&session_id=session-1",
      expect.any(Object)
    );
  });

  it("uses refetched history after later sends in an existing session without local duplicates", async () => {
    const user = userEvent.setup();
    useChatSessionStore.setState({ sessionIdsByStartup: { "startup-1": "session-1" } });
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: "session-1",
          messages: [
            { role: "user", content: "Repeat this", created_at: null, sequence: 1 },
            { role: "assistant", content: "Same reply", created_at: null, sequence: 2 }
          ]
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: "session-1",
          message: "Same reply",
          stage_readiness: null
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          session_id: "session-1",
          messages: [
            { role: "user", content: "Repeat this", created_at: null, sequence: 1 },
            { role: "assistant", content: "Same reply", created_at: null, sequence: 2 },
            { role: "user", content: "Repeat this", created_at: null, sequence: 3 },
            { role: "assistant", content: "Same reply", created_at: null, sequence: 4 }
          ]
        })
      );

    renderWithQueryClient(
      <ChatPanel startupId="startup-1" currentStage="idea" onAdvanceStage={vi.fn()} />
    );

    expect(await screen.findAllByText("Repeat this")).toHaveLength(1);
    await user.type(screen.getByLabelText("Tin nhắn"), "Repeat this");
    await user.click(screen.getByRole("button", { name: "Gửi tin nhắn" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));

    expect(screen.getAllByText("Repeat this")).toHaveLength(2);
    expect(screen.getAllByText("Same reply")).toHaveLength(2);
  });
});
