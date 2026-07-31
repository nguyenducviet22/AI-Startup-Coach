import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
    expect(screen.getByText("No versions yet.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/startups/startup-1/documents/lean_canvas",
      expect.any(Object)
    );
    expect(fetch).toHaveBeenCalledWith(
      "/startups/startup-1/documents/lean_canvas/history",
      expect.any(Object)
    );
  });
});
