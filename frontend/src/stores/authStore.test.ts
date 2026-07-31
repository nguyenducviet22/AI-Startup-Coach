import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiRequest,
  clearAuthTokens,
  getAccessToken,
  getStoredRefreshToken,
  setAccessToken,
  setStoredRefreshToken
} from "../api/client";
import { useAuthStore } from "./authStore";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

describe("auth store bootstrap", () => {
  beforeEach(() => {
    clearAuthTokens();
    useAuthStore.setState({ status: "checking", user: null, error: null });
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    clearAuthTokens();
    vi.unstubAllGlobals();
  });

  it("uses the sessionStorage refresh token on app boot before logging out", async () => {
    setStoredRefreshToken("reload-refresh");
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        user: { id: "user-1", name: "Ada", email: "ada@example.com" },
        access_token: "boot-access",
        refresh_token: "rotated-refresh",
        token_type: "bearer",
        expires_in: 1800
      })
    );

    await useAuthStore.getState().bootstrap();

    expect(fetch).toHaveBeenCalledWith(
      "/auth/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ refresh_token: "reload-refresh" })
      })
    );
    expect(useAuthStore.getState().status).toBe("authenticated");
    expect(useAuthStore.getState().user?.email).toBe("ada@example.com");
    expect(getAccessToken()).toBe("boot-access");
    expect(getStoredRefreshToken()).toBe("rotated-refresh");
  });

  it("routes auth state to unauthenticated when boot-time refresh fails", async () => {
    setStoredRefreshToken("revoked-refresh");
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: { code: "refresh_revoked", message: "Refresh token was revoked." } }, { status: 401 })
    );

    await useAuthStore.getState().bootstrap();

    expect(useAuthStore.getState().status).toBe("unauthenticated");
    expect(useAuthStore.getState().user).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
  });

  it("routes auth state to unauthenticated when a mid-session refresh fails", async () => {
    setAccessToken("expired-access");
    setStoredRefreshToken("revoked-refresh");
    useAuthStore.setState({
      status: "authenticated",
      user: { id: "user-1", name: "Ada", email: "ada@example.com" },
      error: null
    });
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "expired_token", message: "Access token expired." } }, { status: 401 })
      )
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "refresh_revoked", message: "Refresh token revoked." } }, { status: 401 })
      );

    await expect(apiRequest("/startups")).rejects.toThrow("Access token expired.");

    expect(useAuthStore.getState().status).toBe("unauthenticated");
    expect(useAuthStore.getState().user).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
  });
});
