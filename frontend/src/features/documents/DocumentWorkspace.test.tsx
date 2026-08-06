import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAuthTokens } from "../../api/client";
import { DocumentWorkspace } from "./DocumentWorkspace";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("DocumentWorkspace", () => {
  beforeEach(() => {
    clearAuthTokens();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    clearAuthTokens();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows an ungenerated empty state once history resolves", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: "No current document" }, { status: 404 }))
      .mockResolvedValueOnce(jsonResponse({ documents: [] }));

    renderWithQueryClient(
      <DocumentWorkspace startupId="startup-1" selectedDocType="lean_canvas" onSelectDocType={vi.fn()} />
    );

    expect(await screen.findByRole("heading", { name: "No Lean Canvas yet" })).toBeInTheDocument();
    expect(screen.getByText("No previous versions.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/startups/startup-1/documents/lean_canvas",
      expect.any(Object)
    );
    expect(fetch).toHaveBeenCalledWith(
      "/startups/startup-1/documents/lean_canvas/history",
      expect.any(Object)
    );
  });

  it("offers PDF and DOCX downloads for a generated document", async () => {
    const document = {
      id: "doc-1",
      startup_id: "startup-1",
      doc_type: "swot",
      version: 1,
      is_current: true,
      created_at: "2026-08-02T10:00:00Z",
      content: { strengths: ["Hiểu sinh viên"], weaknesses: [], opportunities: [], threats: [] }
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(document))
      .mockResolvedValueOnce(jsonResponse({ documents: [document] }))
      .mockResolvedValueOnce(new Response(new Blob(["pdf"]), {
        status: 200,
        headers: { "Content-Type": "application/pdf", "Content-Disposition": "attachment; filename=ecolearn-swot.pdf" }
      }));
    const createObjectURL = vi.fn(() => "blob:download");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    renderWithQueryClient(
      <DocumentWorkspace startupId="startup-1" startupName="EcoLearn" selectedDocType="swot" onSelectDocType={vi.fn()} />
    );

    const pdfButton = await screen.findByRole("button", { name: "Download PDF" });
    expect(screen.getByRole("button", { name: "Download DOCX" })).toBeInTheDocument();
    await userEvent.click(pdfButton);
    expect(fetch).toHaveBeenLastCalledWith(
      "/startups/startup-1/documents/swot/export?format=pdf",
      expect.any(Object)
    );
  });

  it("clears an old-version preview when switching document types", async () => {
    const user = userEvent.setup();
    const leanCurrent = { id: "lean-2", startup_id: "startup-1", doc_type: "lean_canvas", version: 2, is_current: true, created_at: null, content: { problem: "Current problem" } };
    const leanOld = { ...leanCurrent, id: "lean-1", version: 1, is_current: false, content: { problem: "Old problem" } };
    const swot = { id: "swot-1", startup_id: "startup-1", doc_type: "swot", version: 1, is_current: true, created_at: null, content: { strengths: ["Fast team"], weaknesses: [], opportunities: [], threats: [] } };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(leanCurrent))
      .mockResolvedValueOnce(jsonResponse({ documents: [leanCurrent, leanOld] }))
      .mockResolvedValueOnce(jsonResponse(swot))
      .mockResolvedValueOnce(jsonResponse({ documents: [swot] }));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const { rerender } = render(<QueryClientProvider client={queryClient}><DocumentWorkspace startupId="startup-1" selectedDocType="lean_canvas" onSelectDocType={vi.fn()} /></QueryClientProvider>);

    await user.click(await screen.findByRole("button", { name: "Preview version 1" }));
    expect(screen.getByText("Old problem")).toBeInTheDocument();
    rerender(<QueryClientProvider client={queryClient}><DocumentWorkspace startupId="startup-1" selectedDocType="swot" onSelectDocType={vi.fn()} /></QueryClientProvider>);

    expect(await screen.findByText("Fast team")).toBeInTheDocument();
    expect(screen.queryByText("Old problem")).not.toBeInTheDocument();
  });
});
