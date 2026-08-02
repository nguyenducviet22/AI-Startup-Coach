import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { DocumentType } from "../api/documents";

export type WorkspaceView = "chat" | "documents";
export type WorkspaceDocument = DocumentType | "startup_report";

export type WorkspacePreference = {
  activeView: WorkspaceView;
  selectedDocument: WorkspaceDocument;
  chatDraft: string;
};

type WorkspacePreferencesState = {
  lastStartupId: string | null;
  workspaces: Record<string, WorkspacePreference>;
  getWorkspace: (startupId: string) => WorkspacePreference;
  setLastStartupId: (startupId: string | null) => void;
  updateWorkspace: (startupId: string, patch: Partial<WorkspacePreference>) => void;
  forgetStartup: (startupId: string) => void;
};

const DEFAULT_WORKSPACE: WorkspacePreference = {
  activeView: "chat",
  selectedDocument: "lean_canvas",
  chatDraft: ""
};

export const useWorkspacePreferencesStore = create<WorkspacePreferencesState>()(
  persist(
    (set, get) => ({
      lastStartupId: null,
      workspaces: {},
      getWorkspace: (startupId) => get().workspaces[startupId] ?? DEFAULT_WORKSPACE,
      setLastStartupId: (startupId) => set({ lastStartupId: startupId }),
      updateWorkspace: (startupId, patch) => set((state) => ({
        workspaces: {
          ...state.workspaces,
          [startupId]: { ...(state.workspaces[startupId] ?? DEFAULT_WORKSPACE), ...patch }
        }
      })),
      forgetStartup: (startupId) => set((state) => {
        const workspaces = { ...state.workspaces };
        delete workspaces[startupId];
        return {
          workspaces,
          lastStartupId: state.lastStartupId === startupId ? null : state.lastStartupId
        };
      })
    }),
    {
      name: "ai-startup-coach-workspace",
      version: 1,
      storage: createJSONStorage(() => window.localStorage),
      partialize: (state) => ({ lastStartupId: state.lastStartupId, workspaces: state.workspaces })
    }
  )
);
