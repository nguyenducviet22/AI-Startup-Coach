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
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

onAuthFailure(() => {
  useAuthStore.setState({ status: "unauthenticated", user: null, error: null });
});
