import { create } from "zustand";

type ChatSessionState = {
  sessionIdsByStartup: Record<string, string>;
  getSessionId: (startupId: string) => string | null;
  setSessionId: (startupId: string, sessionId: string | null) => void;
};

export const useChatSessionStore = create<ChatSessionState>((set, get) => ({
  sessionIdsByStartup: {},

  getSessionId(startupId) {
    return get().sessionIdsByStartup[startupId] ?? null;
  },

  setSessionId(startupId, sessionId) {
    set((state) => {
      const next = { ...state.sessionIdsByStartup };
      if (sessionId) {
        next[startupId] = sessionId;
      } else {
        delete next[startupId];
      }
      return { sessionIdsByStartup: next };
    });
  }
}));
