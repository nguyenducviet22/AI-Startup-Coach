import { afterEach, describe, expect, it, vi } from "vitest";

import { runResearch } from "./research";

describe("runResearch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the typed founder request to the startup research endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ evidence: [], cache_hit: false, retrieved_at: "2026-08-07T00:00:00Z", served_at: "2026-08-07T00:00:00Z", legal_notice: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await runResearch("startup-1", { query: "market size", category: "pricing", force_refresh: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/startups/startup-1/research",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "market size", category: "pricing", force_refresh: true })
      })
    );
  });
});
