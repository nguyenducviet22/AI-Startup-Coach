import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest, clearAuthTokens, getAccessToken, getStoredRefreshToken, setAccessToken, setStoredRefreshToken } from "./client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

describe("api client auth handling", () => {
  beforeEach(() => {
    clearAuthTokens();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    clearAuthTokens();
    vi.unstubAllGlobals();
  });

  it("refreshes once on 401, rotates tokens, and retries the original request", async () => {
    setAccessToken("expired-access");
    setStoredRefreshToken("refresh-one");
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: { code: "expired_token", message: "Expired" } }, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({
          user: { id: "user-1", name: "Ada", email: "ada@example.com" },
          access_token: "fresh-access",
          refresh_token: "refresh-two",
          token_type: "bearer",
          expires_in: 1800
        })
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await apiRequest<{ ok: boolean }>("/startups");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect((fetchMock.mock.calls[0][1]?.headers as Headers).get("Authorization")).toBe(
      "Bearer expired-access"
    );
    expect((fetchMock.mock.calls[2][1]?.headers as Headers).get("Authorization")).toBe(
      "Bearer fresh-access"
    );
    expect(getAccessToken()).toBe("fresh-access");
    expect(getStoredRefreshToken()).toBe("refresh-two");
  });

  it("clears tokens when refresh fails", async () => {
    setAccessToken("expired-access");
    setStoredRefreshToken("bad-refresh");
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: { code: "expired_token", message: "Expired" } }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ detail: { code: "refresh_revoked", message: "Revoked" } }, { status: 401 }));

    await expect(apiRequest("/startups")).rejects.toThrow("Expired");

    expect(getAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
  });
});
