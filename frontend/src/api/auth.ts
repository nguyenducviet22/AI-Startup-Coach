import { apiRequest, clearAuthTokens, getStoredRefreshToken, persistTokenBundle } from "./client";
import type { AuthTokenResponse } from "./types";

export type SignupInput = {
  name: string;
  email: string;
  password: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export async function signup(input: SignupInput): Promise<AuthTokenResponse> {
  const tokens = await apiRequest<AuthTokenResponse>("/auth/signup", {
    method: "POST",
    auth: false,
    body: JSON.stringify(input)
  });
  persistTokenBundle(tokens);
  return tokens;
}

export async function login(input: LoginInput): Promise<AuthTokenResponse> {
  const tokens = await apiRequest<AuthTokenResponse>("/auth/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify(input)
  });
  persistTokenBundle(tokens);
  return tokens;
}

export async function logout(): Promise<void> {
  const refreshToken = getStoredRefreshToken();
  clearAuthTokens();
  if (!refreshToken) {
    return;
  }

  await apiRequest("/auth/logout", {
    method: "POST",
    auth: false,
    retryOnUnauthorized: false,
    body: JSON.stringify({ refresh_token: refreshToken })
  }).catch(() => undefined);
}
