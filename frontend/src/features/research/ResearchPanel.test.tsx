import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResearchPanel } from "./ResearchPanel";

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><ResearchPanel startupId="startup-1" sessionId="session-1" /></QueryClientProvider>);
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("ResearchPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits a typed query and renders returned evidence", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ evidence: [{ source_id: "source-1", url: "https://example.com", title: "Source", excerpt: "Evidence", retrieved_at: "2026-08-07T00:00:00Z", published_at: null, authority: "official", legal_or_regulatory: false }], cache_hit: false, retrieved_at: "2026-08-07T00:00:00Z", served_at: "2026-08-07T00:00:00Z", legal_notice: null }));
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await user.type(screen.getByLabelText("Research question"), "market size");
    await user.click(screen.getByRole("button", { name: "Run research" }));

    expect(await screen.findByRole("link", { name: "Source" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/startups/startup-1/research", expect.objectContaining({ body: expect.stringContaining("market size") }));
  });

  it("requires a jurisdiction for legal research and shows a rate-limit error", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: { field: "research", code: "research_rate_limited", message: "Limited" } }, 429));
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await user.type(screen.getByLabelText("Research question"), "licensing");
    await user.selectOptions(screen.getByLabelText("Category"), "legal");
    await user.click(screen.getByRole("button", { name: "Run research" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Jurisdiction is required");

    await user.type(screen.getByLabelText(/Jurisdiction/), "Vietnam");
    await user.click(screen.getByRole("button", { name: "Run research" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Research rate limit reached"));
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("accepts URL extraction input and sends force_refresh when evidence is refreshed", async () => {
    const user = userEvent.setup();
    const response = { evidence: [], cache_hit: false, retrieved_at: "2026-08-07T00:00:00Z", served_at: "2026-08-07T00:00:00Z", legal_notice: null };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await user.type(screen.getByLabelText("Source URLs"), "https://example.com/source");
    await user.click(screen.getByRole("button", { name: "Run research" }));
    await screen.findByRole("button", { name: "Refresh evidence" });
    await user.click(screen.getByRole("button", { name: "Refresh evidence" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[0][1].body).toContain("https://example.com/source");
    expect(fetchMock.mock.calls[1][1].body).toContain("\"force_refresh\":true");
  });
});
