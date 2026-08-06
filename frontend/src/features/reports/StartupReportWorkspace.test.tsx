import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StartupReportWorkspace } from "./StartupReportWorkspace";

describe("StartupReportWorkspace", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("selects available sections and downloads the same selection", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        startup_id: "startup-1",
        startup_name: "EcoLearn",
        sections: [
          { key: "overview", title: "Tổng quan ý tưởng", available: true, content: { problem: "Focus" } },
          { key: "swot", title: "Phân tích SWOT", available: false, content: {} }
        ]
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(new Blob(["pdf"]), { status: 200, headers: { "Content-Disposition": "attachment; filename=ecolearn-startup-report.pdf" } })));
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:report"), revokeObjectURL: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><StartupReportWorkspace startupId="startup-1" /></QueryClientProvider>);

    expect(await screen.findByRole("checkbox", { name: "Tổng quan ý tưởng" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Phân tích SWOT" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Download PDF report" }));
    expect(fetch).toHaveBeenLastCalledWith("/startups/startup-1/report/export?format=pdf&sections=overview", expect.any(Object));
  });
});
