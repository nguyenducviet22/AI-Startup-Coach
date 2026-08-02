import type { ApiErrorBody, AuthTokenResponse } from "./types";

const REFRESH_TOKEN_KEY = "ai-startup-coach.refresh-token";

let accessToken: string | null = null;
let refreshPromise: Promise<AuthTokenResponse> | null = null;
const authFailureListeners = new Set<() => void>();

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(errorMessage(body, status));
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = RequestInit & {
  auth?: boolean;
  retryOnUnauthorized?: boolean;
};

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getStoredRefreshToken(): string | null {
  return window.sessionStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setStoredRefreshToken(token: string | null): void {
  if (token) {
    window.sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
    return;
  }
  window.sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function clearAuthTokens(): void {
  accessToken = null;
  setStoredRefreshToken(null);
}

export function onAuthFailure(callback: () => void): () => void {
  authFailureListeners.add(callback);
  return () => {
    authFailureListeners.delete(callback);
  };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, retryOnUnauthorized = true, headers, ...init } = options;
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: requestHeaders(headers, auth)
  });

  if (response.status === 401 && auth && retryOnUnauthorized) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, retryOnUnauthorized: false });
    }
  }

  return parseResponse<T>(response);
}

export async function refreshAccessToken(): Promise<AuthTokenResponse | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    clearAuthTokens();
    notifyAuthFailure();
    return null;
  }

  if (!refreshPromise) {
    refreshPromise = requestRefresh(refreshToken).finally(() => {
      refreshPromise = null;
    });
  }

  try {
    return await refreshPromise;
  } catch (error) {
    clearAuthTokens();
    if (error instanceof ApiError) {
      notifyAuthFailure();
      return null;
    }
    throw error;
  }
}

async function requestRefresh(refreshToken: string): Promise<AuthTokenResponse> {
  const response = await apiRequest<AuthTokenResponse>("/auth/refresh", {
    method: "POST",
    auth: false,
    retryOnUnauthorized: false,
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  persistTokenBundle(response);
  return response;
}

export function persistTokenBundle(tokens: AuthTokenResponse): void {
  setAccessToken(tokens.access_token);
  setStoredRefreshToken(tokens.refresh_token);
}

function requestHeaders(headers: HeadersInit | undefined, auth: boolean): Headers {
  const nextHeaders = new Headers(headers);
  if (!nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }
  if (auth && accessToken) {
    nextHeaders.set("Authorization", `Bearer ${accessToken}`);
  }
  return nextHeaders;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await parseJson(response);
  if (!response.ok) {
    throw new ApiError(response.status, body as ApiErrorBody | null);
  }
  return body as T;
}

async function parseJson(response: Response): Promise<ApiErrorBody | unknown> {
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  if (!text) {
    return null;
  }
  return JSON.parse(text) as unknown;
}

export function apiUrl(path: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";
  return `${baseUrl}${path}`;
}

function errorMessage(body: ApiErrorBody | null, status: number): string {
  if (typeof body?.detail === "string") {
    return body.detail;
  }
  if (body?.detail && typeof body.detail === "object") {
    return body.detail.message;
  }
  return `Request failed with status ${status}`;
}

function notifyAuthFailure(): void {
  authFailureListeners.forEach((callback) => callback());
}
