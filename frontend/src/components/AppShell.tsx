import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useState } from "react";

import type { DocumentType } from "../api/documents";
import {
  advanceStartupStage,
  createStartup,
  listStartups,
  setStartupStage,
  type StageName,
  type Startup,
  type StartupListResponse
} from "../api/startups";
import { ChatPanel } from "../features/chat/ChatPanel";
import { DOCUMENT_LABELS, stageToDocumentType } from "../features/documents/documentTypes";
import { DocumentWorkspace } from "../features/documents/DocumentWorkspace";
import { StageControls } from "../features/stages/StageControls";
import { STAGE_LABELS } from "../features/stages/stageLabels";
import { useAuthStore } from "../stores/authStore";

export function AppShell() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const queryClient = useQueryClient();
  const [selectedStartupId, setSelectedStartupId] = useState<string | null>(null);
  const startupsQuery = useQuery({
    queryKey: ["startups"],
    queryFn: listStartups
  });
  const startups = startupsQuery.data?.startups ?? [];
  const selectedStartup = useMemo(
    () => startups.find((startup) => startup.id === selectedStartupId) ?? startups[0] ?? null,
    [selectedStartupId, startups]
  );

  const createMutation = useMutation({
    mutationFn: createStartup,
    onSuccess(startup) {
      queryClient.setQueryData<StartupListResponse>(["startups"], (current) => ({
        startups: [startup, ...(current?.startups ?? [])]
      }));
      setSelectedStartupId(startup.id);
    }
  });

  const advanceMutation = useMutation({
    mutationFn: advanceStartupStage,
    onSuccess: (startup) => updateStartupCache(queryClient, startup)
  });

  const setStageMutation = useMutation({
    mutationFn: ({ startupId, stage }: { startupId: string; stage: StageName }) =>
      setStartupStage(startupId, stage),
    onSuccess: (startup) => updateStartupCache(queryClient, startup)
  });

  function handleCreateStartup(name: string | null) {
    createMutation.mutate(name);
  }

  function handleAdvanceStage() {
    if (!selectedStartup || selectedStartup.current_stage === "completed") {
      return;
    }
    advanceMutation.mutate(selectedStartup.id);
  }

  function handleSetStage(stage: StageName) {
    if (!selectedStartup) {
      return;
    }
    setStageMutation.mutate({ startupId: selectedStartup.id, stage });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI Startup Coach</p>
          <h1>Workspace</h1>
        </div>
        <div className="account">
          <span>{user?.name}</span>
          <button type="button" className="secondary-button" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </header>

      <div className="workspace-layout">
        <aside className="startup-sidebar" aria-label="Startups">
          <CreateStartupForm
            isCreating={createMutation.isPending}
            error={createMutation.error}
            onCreate={handleCreateStartup}
          />

          <StartupList
            startups={startups}
            selectedStartupId={selectedStartup?.id ?? null}
            isLoading={startupsQuery.isLoading}
            error={startupsQuery.error}
            onSelect={setSelectedStartupId}
          />
        </aside>

        <section className="workspace-main">
          {selectedStartup ? (
            <StartupWorkspace
              startup={selectedStartup}
              isAdvancing={advanceMutation.isPending}
              isSettingStage={setStageMutation.isPending}
              mutationError={advanceMutation.error ?? setStageMutation.error}
              onAdvanceStage={handleAdvanceStage}
              onSetStage={handleSetStage}
            />
          ) : (
            <section className="empty-workspace">
              <h2>Ready for your first startup</h2>
              <p>Create a workspace to begin the coaching flow.</p>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

type CreateStartupFormProps = {
  isCreating: boolean;
  error: Error | null;
  onCreate: (name: string | null) => void;
};

function CreateStartupForm({ isCreating, error, onCreate }: CreateStartupFormProps) {
  const [name, setName] = useState("");

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(name.trim() || null);
    setName("");
  }

  return (
    <form className="create-startup-form" onSubmit={onSubmit}>
      <label>
        New startup
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="TutorOS"
          maxLength={120}
        />
      </label>
      {error ? <p className="form-error">{error.message}</p> : null}
      <button type="submit" className="primary-button" disabled={isCreating}>
        {isCreating ? "Creating..." : "Create"}
      </button>
    </form>
  );
}

type StartupListProps = {
  startups: Startup[];
  selectedStartupId: string | null;
  isLoading: boolean;
  error: Error | null;
  onSelect: (startupId: string) => void;
};

function StartupList({ startups, selectedStartupId, isLoading, error, onSelect }: StartupListProps) {
  if (isLoading) {
    return <p className="sidebar-note">Loading startups...</p>;
  }

  if (error) {
    return <p className="form-error">{error.message}</p>;
  }

  if (startups.length === 0) {
    return <p className="sidebar-note">No startups yet.</p>;
  }

  return (
    <div className="startup-list">
      {startups.map((startup) => (
        <button
          type="button"
          className={startup.id === selectedStartupId ? "startup-list-item selected" : "startup-list-item"}
          onClick={() => onSelect(startup.id)}
          key={startup.id}
        >
          <span>{startup.name ?? "Untitled startup"}</span>
          <small>{STAGE_LABELS[startup.current_stage]}</small>
        </button>
      ))}
    </div>
  );
}

type StartupWorkspaceProps = {
  startup: Startup;
  isAdvancing: boolean;
  isSettingStage: boolean;
  mutationError: Error | null;
  onAdvanceStage: () => void;
  onSetStage: (stage: StageName) => void;
};

function StartupWorkspace({
  startup,
  isAdvancing,
  isSettingStage,
  mutationError,
  onAdvanceStage,
  onSetStage
}: StartupWorkspaceProps) {
  const currentStageDocType = stageToDocumentType(startup.current_stage);
  const [selectedDocType, setSelectedDocType] = useState<DocumentType>(currentStageDocType ?? "lean_canvas");

  useEffect(() => {
    setSelectedDocType(stageToDocumentType(startup.current_stage) ?? "lean_canvas");
  }, [startup.id, startup.current_stage]);

  function openCurrentDocument() {
    if (!currentStageDocType) {
      return;
    }
    setSelectedDocType(currentStageDocType);
    document.getElementById("documents")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <section className="workspace-header">
        <div>
          <p className="eyebrow">Startup</p>
          <h2>{startup.name ?? "Untitled startup"}</h2>
        </div>
        <div className="workspace-header-actions">
          {currentStageDocType ? (
            <button type="button" className="secondary-button" onClick={openCurrentDocument}>
              View {DOCUMENT_LABELS[currentStageDocType]}
            </button>
          ) : null}
          <span className="status-pill">{STAGE_LABELS[startup.current_stage]}</span>
        </div>
      </section>

      <StageControls
        currentStage={startup.current_stage}
        isAdvancing={isAdvancing}
        isSettingStage={isSettingStage}
        onAdvanceStage={onAdvanceStage}
        onSetStage={onSetStage}
      />

      {mutationError ? <p className="form-error">{mutationError.message}</p> : null}

      <DocumentWorkspace
        startupId={startup.id}
        selectedDocType={selectedDocType}
        onSelectDocType={setSelectedDocType}
      />

      <ChatPanel
        startupId={startup.id}
        currentStage={startup.current_stage}
        isAdvancing={isAdvancing}
        onAdvanceStage={onAdvanceStage}
        currentDocumentLabel={currentStageDocType ? DOCUMENT_LABELS[currentStageDocType] : null}
        onOpenCurrentDocument={currentStageDocType ? openCurrentDocument : undefined}
      />
    </>
  );
}

function updateStartupCache(queryClient: ReturnType<typeof useQueryClient>, startup: Startup): void {
  queryClient.setQueryData<StartupListResponse>(["startups"], (current) => ({
    startups: (current?.startups ?? []).map((item) => (item.id === startup.id ? startup : item))
  }));
}
