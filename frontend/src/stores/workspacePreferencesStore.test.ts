import { beforeEach, describe, expect, it } from "vitest";

import { useWorkspacePreferencesStore } from "./workspacePreferencesStore";

describe("workspacePreferencesStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useWorkspacePreferencesStore.setState({ lastStartupId: null, workspaces: {} });
  });

  it("keeps view, document, and draft independently per startup", () => {
    const state = useWorkspacePreferencesStore.getState();
    state.setLastStartupId("startup-2");
    state.updateWorkspace("startup-1", { activeView: "documents", selectedDocument: "swot", chatDraft: "Draft one" });
    state.updateWorkspace("startup-2", { activeView: "chat", selectedDocument: "marketing", chatDraft: "Draft two" });

    expect(useWorkspacePreferencesStore.getState().lastStartupId).toBe("startup-2");
    expect(useWorkspacePreferencesStore.getState().getWorkspace("startup-1")).toMatchObject({
      activeView: "documents",
      selectedDocument: "swot",
      chatDraft: "Draft one"
    });
    expect(useWorkspacePreferencesStore.getState().getWorkspace("startup-2")).toMatchObject({
      activeView: "chat",
      selectedDocument: "marketing",
      chatDraft: "Draft two"
    });
  });

  it("falls back to safe defaults and can forget a stale startup", () => {
    expect(useWorkspacePreferencesStore.getState().getWorkspace("missing")).toEqual({
      activeView: "chat",
      selectedDocument: "lean_canvas",
      chatDraft: ""
    });

    useWorkspacePreferencesStore.getState().setLastStartupId("missing");
    useWorkspacePreferencesStore.getState().updateWorkspace("missing", { chatDraft: "stale" });
    useWorkspacePreferencesStore.getState().forgetStartup("missing");

    expect(useWorkspacePreferencesStore.getState().lastStartupId).toBeNull();
    expect(useWorkspacePreferencesStore.getState().getWorkspace("missing").chatDraft).toBe("");
  });
});
