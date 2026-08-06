import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type { DocumentType } from "../api/documents";
import { updateLocalProfile } from "../api/profile";
import {
  advanceStartupStage,
  createStartup,
  listStartups,
  renameStartup,
  setStartupStage,
  type StageName,
  type Startup,
  type StartupListResponse
} from "../api/startups";
import { ChatPanel } from "../features/chat/ChatPanel";
import { DOCUMENT_LABELS, stageToDocumentType } from "../features/documents/documentTypes";
import { DocumentWorkspace } from "../features/documents/DocumentWorkspace";
import { StartupOverview } from "../features/overview/StartupOverview";
import { StartupReportWorkspace } from "../features/reports/StartupReportWorkspace";
import { StageControls } from "../features/stages/StageControls";
import { STAGES, STAGE_LABELS, nextStageLabel } from "../features/stages/stageLabels";
import { useToastStore } from "../stores/toastStore";
import { useWorkspacePreferencesStore, type WorkspaceView } from "../stores/workspacePreferencesStore";
import { ConfirmationDialog } from "./ConfirmationDialog";
import { OpenRouterKeyControl } from "./OpenRouterKeyControl";
import { Skeleton } from "./Skeleton";

type PendingAction = { kind: "advance" } | { kind: "set-stage"; stage: StageName } | null;

export function AppShell({ profileName }: { profileName: string }) {
  const showToast = useToastStore((state) => state.showToast);
  const queryClient = useQueryClient();
  const storedStartupId = useWorkspacePreferencesStore((state) => state.lastStartupId);
  const setLastStartupId = useWorkspacePreferencesStore((state) => state.setLastStartupId);
  const [selectedStartupId, setSelectedStartupId] = useState<string | null>(storedStartupId);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileDraft, setProfileDraft] = useState(profileName);
  const startupsQuery = useQuery({ queryKey: ["startups"], queryFn: listStartups });
  const startups = startupsQuery.data?.startups ?? [];
  const orderedStartups = useMemo(() => sortStartupsByRecent(startups), [startups]);
  const selectedStartup = useMemo(
    () => orderedStartups.find((startup) => startup.id === selectedStartupId) ?? orderedStartups[0] ?? null,
    [selectedStartupId, orderedStartups]
  );

  useEffect(() => setProfileDraft(profileName), [profileName]);
  useEffect(() => {
    if (startupsQuery.isLoading) return;
    const resolvedId = orderedStartups.some((startup) => startup.id === selectedStartupId)
      ? selectedStartupId
      : orderedStartups[0]?.id ?? null;
    if (resolvedId !== selectedStartupId) setSelectedStartupId(resolvedId);
    if (resolvedId !== storedStartupId) setLastStartupId(resolvedId);
  }, [orderedStartups, selectedStartupId, setLastStartupId, startupsQuery.isLoading, storedStartupId]);

  function selectStartup(startupId: string) {
    setSelectedStartupId(startupId);
    setLastStartupId(startupId);
    setIsSidebarOpen(false);
  }

  const profileMutation = useMutation({
    mutationFn: updateLocalProfile,
    onSuccess(profile) {
      queryClient.setQueryData(["profile"], profile);
      setIsEditingProfile(false);
      showToast("Your name was updated.", "success");
    },
    onError: () => showToast("Unable to update your name. Please try again.", "error")
  });

  const createMutation = useMutation({
    mutationFn: createStartup,
    onSuccess(startup) {
      queryClient.setQueryData<StartupListResponse>(["startups"], (current) => ({
        startups: [startup, ...(current?.startups ?? [])]
      }));
      setSelectedStartupId(startup.id);
      setLastStartupId(startup.id);
      setIsSidebarOpen(false);
      showToast("New startup created.", "success");
    },
    onError: () => showToast("Unable to create startup. Please try again.", "error")
  });

  const renameMutation = useMutation({
    mutationFn: ({ startupId, name }: { startupId: string; name: string }) => renameStartup(startupId, name),
    onSuccess(startup) {
      updateStartupCache(queryClient, startup);
      showToast("Startup renamed.", "success");
    },
    onError: () => showToast("Unable to rename startup. Please try again.", "error")
  });

  const advanceMutation = useMutation({
    mutationFn: advanceStartupStage,
    onSuccess(startup) {
      updateStartupCache(queryClient, startup);
      void queryClient.invalidateQueries({ queryKey: ["startup-overview", startup.id] });
      showToast(`Moved to ${STAGE_LABELS[startup.current_stage]}.`, "success");
    },
    onError: () => showToast("Unable to advance the stage. Please try again.", "error")
  });

  const setStageMutation = useMutation({
    mutationFn: ({ startupId, stage }: { startupId: string; stage: StageName }) => setStartupStage(startupId, stage),
    onSuccess(startup) {
      updateStartupCache(queryClient, startup);
      void queryClient.invalidateQueries({ queryKey: ["startup-overview", startup.id] });
      showToast(`Returned to ${STAGE_LABELS[startup.current_stage]}.`, "success");
    },
    onError: () => showToast("Unable to update the stage. Please try again.", "error")
  });

  function confirmPendingAction() {
    const action = pendingAction;
    setPendingAction(null);
    if (!action || !selectedStartup) return;
    if (action.kind === "advance" && selectedStartup.current_stage !== "completed") {
      advanceMutation.mutate(selectedStartup.id);
    } else if (action.kind === "set-stage") {
      setStageMutation.mutate({ startupId: selectedStartup.id, stage: action.stage });
    }
  }

  const dialogCopy = confirmationCopy(pendingAction, selectedStartup);

  return (
    <main className="app-shell">
      <header className="topbar">
        <strong className="tool-wordmark">AI Startup Coach</strong>
        <div className="account">
          <OpenRouterKeyControl />
          {isEditingProfile ? (
            <form className="account-edit" onSubmit={(event) => { event.preventDefault(); if (profileDraft.trim()) profileMutation.mutate(profileDraft.trim()); }}>
              <label className="sr-only" htmlFor="account-name">Your name</label>
              <input id="account-name" value={profileDraft} onChange={(event) => setProfileDraft(event.target.value)} maxLength={255} autoFocus />
              <button type="submit" className="text-button" disabled={!profileDraft.trim() || profileMutation.isPending}>Save</button>
              <button type="button" className="text-button muted" onClick={() => { setProfileDraft(profileName); setIsEditingProfile(false); }}>Cancel</button>
            </form>
          ) : (
            <button type="button" className="account-button" onClick={() => setIsEditingProfile(true)} aria-label="Rename user">
              <span className="account-copy"><strong>{profileName}</strong><span>Founder</span></span>
            </button>
          )}
        </div>
      </header>

      <button type="button" className="mobile-sidebar-toggle" aria-expanded={isSidebarOpen} aria-controls="startup-sidebar" onClick={() => setIsSidebarOpen((current) => !current)}>
        <span>Your startups</span><strong>{selectedStartup?.name ?? "None selected"}</strong><span aria-hidden="true">{isSidebarOpen ? "Collapse ↑" : "Open list ↓"}</span>
      </button>

      <div className="workspace-layout">
        <aside id="startup-sidebar" className="startup-sidebar" data-open={isSidebarOpen} aria-label="Startup list">
          <div className="sidebar-heading"><div><p className="eyebrow">Workspace</p><h2>Your startups</h2></div><span className="count-badge">{startups.length}</span></div>
          <CreateStartupForm isCreating={createMutation.isPending} error={createMutation.error} onCreate={(name) => createMutation.mutate(name)} />
          <StartupList startups={orderedStartups} selectedStartupId={selectedStartup?.id ?? null} isLoading={startupsQuery.isLoading} error={startupsQuery.error} onSelect={selectStartup} />
        </aside>

        <section className="workspace-main">
          {selectedStartup ? (
            <StartupWorkspace
              startup={selectedStartup}
              isAdvancing={advanceMutation.isPending}
              isSettingStage={setStageMutation.isPending}
              isRenaming={renameMutation.isPending}
              mutationError={advanceMutation.error ?? setStageMutation.error ?? renameMutation.error}
              onRename={(name) => renameMutation.mutate({ startupId: selectedStartup.id, name })}
              onAdvanceStage={() => setPendingAction({ kind: "advance" })}
              onSetStage={(stage) => setPendingAction({ kind: "set-stage", stage })}
            />
          ) : startupsQuery.isLoading ? (
            <section className="workspace-section"><Skeleton lines={6} /></section>
          ) : (
            <section className="empty-workspace"><p className="eyebrow">Start here</p><h2>Create your first startup</h2><p>Name your idea; AI Coach will guide you through each stage.</p><button type="button" className="primary-button mobile-only" onClick={() => setIsSidebarOpen(true)}>Create startup</button></section>
          )}
        </section>
      </div>

      <ConfirmationDialog open={pendingAction !== null} title={dialogCopy.title} description={dialogCopy.description} confirmLabel={dialogCopy.confirmLabel} onConfirm={confirmPendingAction} onCancel={() => setPendingAction(null)} />
    </main>
  );
}

function CreateStartupForm({ isCreating, error, onCreate }: { isCreating: boolean; error: Error | null; onCreate: (name: string | null) => void }) {
  const [name, setName] = useState("");
  function onSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onCreate(name.trim() || null); setName(""); }
  return <form className="create-startup-form" onSubmit={onSubmit}><label>Create a new startup<input type="text" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. TutorOS" maxLength={120} /></label>{error ? <p className="form-error">{error.message}</p> : null}<button type="submit" className="primary-button" disabled={isCreating}>{isCreating ? "Creating..." : "+ Create startup"}</button></form>;
}

type StartupFilter = "all" | "active" | "completed";

export function StartupList({ startups, selectedStartupId, isLoading, error, onSelect }: { startups: Startup[]; selectedStartupId: string | null; isLoading: boolean; error: Error | null; onSelect: (startupId: string) => void }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<StartupFilter>("all");
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const visibleStartups = useMemo(() => {
    const normalizedQuery = normalizeSearchText(query);
    return startups.filter((startup) => {
      const matchesQuery = !normalizedQuery || normalizeSearchText(startup.name ?? "Unnamed startup").includes(normalizedQuery);
      const matchesFilter = filter === "all" || (filter === "completed" ? startup.current_stage === "completed" : startup.current_stage !== "completed");
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, startups]);

  useEffect(() => {
    if (!selectedStartupId) return;
    const selectedElement = scrollContainerRef.current?.querySelector<HTMLElement>(`[data-startup-id="${selectedStartupId}"]`);
    selectedElement?.scrollIntoView?.({ block: "nearest" });
  }, [selectedStartupId, visibleStartups]);

  if (isLoading) return <Skeleton lines={3} compact />;
  if (error) return <p className="form-error">{error.message}</p>;
  if (startups.length === 0) return <div className="sidebar-empty"><strong>No startups yet</strong><p>Create your first startup to begin.</p></div>;
  return <section className="startup-directory" aria-label="Manage startup list">
    <div className="startup-list-toolbar">
      <label className="startup-search">
        <span className="sr-only">Search startups</span>
        <input type="search" aria-label="Search startups" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search startups..." />
      </label>
      <div className="startup-filters" role="group" aria-label="Filter startups">
        <FilterButton label="All" value="all" current={filter} onSelect={setFilter} />
        <FilterButton label="Active" value="active" current={filter} onSelect={setFilter} />
        <FilterButton label="Completed" value="completed" current={filter} onSelect={setFilter} />
      </div>
      <p className="startup-result-count" aria-live="polite">{visibleStartups.length}/{startups.length} startup</p>
    </div>
    <div className="startup-list-scroll" ref={scrollContainerRef} tabIndex={0} aria-label="Scrollable startup list">
      {visibleStartups.length === 0 ? (
        <div className="sidebar-empty filtered-empty"><strong>No matching startups</strong><p>Try another search term or filter.</p></div>
      ) : (
        <div className="startup-list">{visibleStartups.map((startup) => {
          const progress = stageProgress(startup.current_stage);
          return <button type="button" data-startup-id={startup.id} className={startup.id === selectedStartupId ? "startup-list-item selected" : "startup-list-item"} onClick={() => onSelect(startup.id)} key={startup.id} aria-current={startup.id === selectedStartupId ? "true" : undefined}>
            <span className="startup-item-copy"><strong>{startup.name ?? "Unnamed startup"}</strong><small>{STAGE_LABELS[startup.current_stage]} · {progress}/8 stages</small><small>{formatUpdatedAt(startup.updated_at)}</small></span><span aria-hidden="true">›</span>
          </button>;
        })}</div>
      )}
    </div>
  </section>;
}

function FilterButton({ label, value, current, onSelect }: { label: string; value: StartupFilter; current: StartupFilter; onSelect: (filter: StartupFilter) => void }) {
  const selected = value === current;
  return <button type="button" className={selected ? "selected" : ""} aria-pressed={selected} onClick={() => onSelect(value)}>{label}</button>;
}

export function StartupNameControl({ name, isRenaming, onRename }: { name: string; isRenaming: boolean; onRename: (name: string) => void }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const controlRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => { setDraft(name); setIsEditing(false); setMenuPosition(null); }, [name]);
  useEffect(() => {
    if (!menuPosition) return;
    function closeMenu(event: PointerEvent) {
      if (!controlRef.current?.contains(event.target as Node)) setMenuPosition(null);
    }
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuPosition(null);
    }
    document.addEventListener("pointerdown", closeMenu);
    document.addEventListener("keydown", handleKeydown);
    return () => {
      document.removeEventListener("pointerdown", closeMenu);
      document.removeEventListener("keydown", handleKeydown);
    };
  }, [menuPosition]);

  function openMenu(x: number, y: number) {
    setMenuPosition({ x: Math.max(8, Math.min(x, window.innerWidth - 176)), y: Math.max(8, Math.min(y, window.innerHeight - 64)) });
  }

  if (isEditing) {
    return <form className="startup-name-edit" onSubmit={(event) => { event.preventDefault(); if (draft.trim()) { onRename(draft.trim()); setIsEditing(false); } }}>
      <label className="sr-only" htmlFor="startup-name">Startup name</label><input id="startup-name" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={255} autoFocus />
      <button type="submit" className="secondary-button compact-button" disabled={!draft.trim() || isRenaming}>Save</button><button type="button" className="text-button muted" onClick={() => { setDraft(name); setIsEditing(false); }}>Cancel</button>
    </form>;
  }

  return <div className="startup-name-control" ref={controlRef}>
    <h1 ref={titleRef} tabIndex={0} title="Right-click to rename" aria-haspopup="menu" aria-expanded={Boolean(menuPosition)} onContextMenu={(event) => { event.preventDefault(); openMenu(event.clientX, event.clientY); }} onKeyDown={(event) => {
      if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
        event.preventDefault();
        const bounds = titleRef.current?.getBoundingClientRect();
        openMenu(bounds?.left ?? 8, bounds?.bottom ?? 8);
      }
    }}>{name}</h1>
    {menuPosition ? <div className="startup-context-menu" role="menu" aria-label={`Options for ${name}`} style={{ left: menuPosition.x, top: menuPosition.y }}>
      <button type="button" role="menuitem" autoFocus onClick={() => { setMenuPosition(null); setIsEditing(true); }}>Rename startup</button>
    </div> : null}
  </div>;
}

function StartupWorkspace({ startup, isAdvancing, isSettingStage, isRenaming, mutationError, onRename, onAdvanceStage, onSetStage }: { startup: Startup; isAdvancing: boolean; isSettingStage: boolean; isRenaming: boolean; mutationError: Error | null; onRename: (name: string) => void; onAdvanceStage: () => void; onSetStage: (stage: StageName) => void }) {
  const currentStageDocType = stageToDocumentType(startup.current_stage);
  const savedWorkspace = useWorkspacePreferencesStore((state) => state.workspaces[startup.id]);
  const updateWorkspace = useWorkspacePreferencesStore((state) => state.updateWorkspace);
  const selectedDocument = savedWorkspace?.selectedDocument ?? currentStageDocType ?? "lean_canvas";
  const selectedDocType: DocumentType = selectedDocument === "startup_report" ? "lean_canvas" : selectedDocument;
  const activeView: WorkspaceView = savedWorkspace?.activeView ?? "chat";

  useEffect(() => {
    if (!savedWorkspace) {
      updateWorkspace(startup.id, { activeView: "chat", selectedDocument: currentStageDocType ?? "lean_canvas" });
    }
  }, [currentStageDocType, savedWorkspace, startup.id, updateWorkspace]);

  function openCurrentDocument() { if (currentStageDocType) { updateWorkspace(startup.id, { selectedDocument: currentStageDocType, activeView: "documents" }); } }

  return <>
    <section className="workspace-header">
      <div>
        <p className="eyebrow">Current startup</p>
        <StartupNameControl name={startup.name ?? "Unnamed startup"} isRenaming={isRenaming} onRename={onRename} />
        <p>Stage {stageProgress(startup.current_stage)}/8 · {STAGE_LABELS[startup.current_stage]}</p>
      </div>
    </section>

    <StageControls currentStage={startup.current_stage} isAdvancing={isAdvancing} isSettingStage={isSettingStage} onAdvanceStage={onAdvanceStage} onSetStage={onSetStage} />

    <StartupOverview startupId={startup.id} currentStage={startup.current_stage} onContinue={() => updateWorkspace(startup.id, { activeView: "chat" })} />

    <div className="content-switcher" role="tablist" aria-label="Workspace content">
      <button type="button" role="tab" aria-selected={activeView === "chat"} className={activeView === "chat" ? "selected" : ""} onClick={() => updateWorkspace(startup.id, { activeView: "chat" })}>AI Coach</button>
      <button type="button" role="tab" aria-selected={activeView === "documents"} className={activeView === "documents" ? "selected" : ""} onClick={() => updateWorkspace(startup.id, { activeView: "documents" })}>Documents</button>
    </div>

    {mutationError ? <p className="form-error panel-error">{mutationError.message}</p> : null}
    <div role="tabpanel">
      {activeView === "chat" ? <ChatPanel startupId={startup.id} currentStage={startup.current_stage} isAdvancing={isAdvancing} onAdvanceStage={onAdvanceStage} currentDocumentLabel={currentStageDocType ? DOCUMENT_LABELS[currentStageDocType] : null} onOpenCurrentDocument={currentStageDocType ? openCurrentDocument : undefined} /> : null}
      {activeView === "documents" && selectedDocument === "startup_report" ? <StartupReportWorkspace startupId={startup.id} onBack={() => updateWorkspace(startup.id, { selectedDocument: currentStageDocType ?? "lean_canvas" })} /> : null}
      {activeView === "documents" && selectedDocument !== "startup_report" ? <DocumentWorkspace startupId={startup.id} startupName={startup.name ?? "Unnamed startup"} selectedDocType={selectedDocType} onSelectDocType={(docType) => updateWorkspace(startup.id, { selectedDocument: docType })} onOpenReport={() => updateWorkspace(startup.id, { selectedDocument: "startup_report" })} /> : null}
    </div>
  </>;
}

function confirmationCopy(action: PendingAction, startup: Startup | null) {
  if (action?.kind === "set-stage") return { title: `Return to ${STAGE_LABELS[action.stage]}?`, description: "Your generated documents will be preserved.", confirmLabel: "Return to stage" };
  const next = startup ? nextStageLabel(startup.current_stage) : null;
  return { title: next ? `Move to ${next}?` : "Change stage?", description: "Make sure you have provided enough information for the current stage.", confirmLabel: "Continue" };
}

function stageProgress(stage: StageName): number { return stage === "completed" ? 8 : STAGES.indexOf(stage) + 1; }

function formatUpdatedAt(value: string | null): string {
  if (!value) return "No update time";
  const deltaMinutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60_000));
  if (deltaMinutes < 1) return "Updated just now";
  if (deltaMinutes < 60) return `Updated ${deltaMinutes} minutes ago`;
  if (deltaMinutes < 1_440) return `Updated ${Math.floor(deltaMinutes / 60)} hours ago`;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(value));
}

function normalizeSearchText(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLocaleLowerCase("en-US").trim();
}

export function sortStartupsByRecent(startups: Startup[]): Startup[] {
  return [...startups].sort((left, right) => startupTimestamp(right) - startupTimestamp(left));
}

function startupTimestamp(startup: Startup): number {
  const value = startup.updated_at ?? startup.created_at;
  return value ? new Date(value).getTime() : 0;
}

function updateStartupCache(queryClient: ReturnType<typeof useQueryClient>, startup: Startup) {
  queryClient.setQueryData<StartupListResponse>(["startups"], (current) => ({ startups: (current?.startups ?? []).map((item) => item.id === startup.id ? startup : item) }));
}
