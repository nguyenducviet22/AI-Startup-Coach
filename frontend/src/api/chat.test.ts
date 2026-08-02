import { afterEach, describe, expect, it, vi } from "vitest";

import { setStoredOpenRouterApiKey } from "./client";
import { sendChatMessage } from "./chat";

describe("sendChatMessage", () => {
  afterEach(() => {
    setStoredOpenRouterApiKey(null);
    vi.unstubAllGlobals();
  });

  it("sends the session OpenRouter key only with chat requests", async () => {
    setStoredOpenRouterApiKey("sk-or-v1-user-key");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_id: "session-1", message: "Hi", stage_readiness: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendChatMessage("startup-1", "Hello", null);

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-OpenRouter-Api-Key")).toBe("sk-or-v1-user-key");
  });

  it("omits the OpenRouter header when no session key is configured", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_id: "session-1", message: "Hi", stage_readiness: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendChatMessage("startup-1", "Hello", null);

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.has("X-OpenRouter-Api-Key")).toBe(false);
  });
});
