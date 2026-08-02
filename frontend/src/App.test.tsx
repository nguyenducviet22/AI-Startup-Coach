import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><App /></QueryClientProvider>);
}

describe("local profile onboarding", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks only for a name when the local profile is not configured", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ name: "", configured: false }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    })));

    renderApp();

    expect(await screen.findByRole("heading", { name: "Mình nên gọi bạn là gì?" })).toBeInTheDocument();
    expect(screen.getByLabelText("Tên của bạn")).toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/mật khẩu/i)).not.toBeInTheDocument();
  });
});
