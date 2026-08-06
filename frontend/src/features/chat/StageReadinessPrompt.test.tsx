import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StageReadinessPrompt } from "./StageReadinessPrompt";

describe("StageReadinessPrompt", () => {
  it("renders an advance confirmation only when readiness is true", async () => {
    const onAdvanceStage = vi.fn();
    render(
      <StageReadinessPrompt
        readiness={{ ready: true, missing_fields: [] }}
        currentStage="lean_canvas"
        onAdvanceStage={onAdvanceStage}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Continue to Business Model" }));

    expect(onAdvanceStage).toHaveBeenCalledOnce();
    expect(screen.getByText("Ready for the next stage")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /collapse readiness/i })).not.toBeInTheDocument();
  });

  it("collapses and expands missing fields when readiness is false", async () => {
    render(
      <StageReadinessPrompt
        readiness={{ ready: false, missing_fields: ["customer_segments", "channels"] }}
        currentStage="lean_canvas"
        onAdvanceStage={vi.fn()}
      />
    );

    expect(screen.getByText("More information needed")).toBeInTheDocument();
    expect(screen.getByText("Customer segments")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /continue/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Collapse readiness notice" }));

    expect(screen.getByText("More information needed")).toBeInTheDocument();
    expect(screen.queryByText("Customer segments")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Expand readiness notice" }));

    expect(screen.getByText("Customer segments")).toBeInTheDocument();
  });

  it("does not render in the completed stage", () => {
    const { container } = render(
      <StageReadinessPrompt
        readiness={{ ready: true, missing_fields: [] }}
        currentStage="completed"
        onAdvanceStage={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
