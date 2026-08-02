import { create } from "zustand";

import * as authApi from "../api/auth";
import { onAuthFailure, refreshAccessToken } from "../api/client";
import type { AuthUser } from "../api/types";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

type AuthState = {
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  bootstrap: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  status: "checking",
  user: null,
  error: null,

  async bootstrap() {
    set({ status: "checking", error: null });
    const tokens = await refreshAccessToken();
    if (!tokens) {
      set({ status: "unauthenticated", user: null });
      return;
    }
    set({ status: "authenticated", user: tokens.user });
  },

  async login(email, password) {
    set({ error: null });
    try {
      const tokens = await authApi.login({ email, password });
      set({ status: "authenticated", user: tokens.user });
    } catch (error) {
      set({ status: "unauthenticated", user: null, error: messageFromError(error) });
      throw error;
    }
  },

  async signup(name, email, password) {
    set({ error: null });
    try {
      const tokens = await authApi.signup({ name, email, password });
      set({ status: "authenticated", user: tokens.user });
    } catch (error) {
      set({ status: "unauthenticated", user: null, error: messageFromError(error) });
      throw error;
    }
  },

  async logout() {
    set({ error: null });
    await authApi.logout();
    set({ status: "unauthenticated", user: null });
  },

  clearError() {
    set({ error: null });
  }
}));

function messageFromError(error: unknown): string {
  if (error instanceof Error) {
    return AUTH_ERROR_MESSAGES[error.message] ?? error.message;
  }
  return "Đã có lỗi xảy ra. Vui lòng thử lại.";
}

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  "Email is already registered.": "Email này đã được đăng ký.",
  "Email or password is incorrect.": "Email hoặc mật khẩu không chính xác.",
  "Refresh token is required.": "Phiên đăng nhập không hợp lệ.",
  "Refresh token is invalid.": "Phiên đăng nhập không hợp lệ.",
  "Refresh token has expired.": "Phiên đăng nhập đã hết hạn.",
  "Refresh token reuse was detected.": "Phiên đăng nhập không còn an toàn. Vui lòng đăng nhập lại.",
  "Refresh token has been revoked.": "Phiên đăng nhập đã kết thúc."
};

onAuthFailure(() => {
  useAuthStore.setState({ status: "unauthenticated", user: null, error: null });
});
