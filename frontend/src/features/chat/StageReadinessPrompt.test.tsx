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

    await userEvent.click(screen.getByRole("button", { name: "Advance to Business Model" }));

    expect(screen.getByText("Ready for the next stage")).toBeInTheDocument();
    expect(onAdvanceStage).toHaveBeenCalledOnce();
  });

  it("renders missing fields when readiness is false", () => {
    render(
      <StageReadinessPrompt
        readiness={{ ready: false, missing_fields: ["customer_segments", "channels"] }}
        currentStage="lean_canvas"
        onAdvanceStage={vi.fn()}
      />
    );

    expect(screen.getByText("More context needed")).toBeInTheDocument();
    expect(screen.getByText("customer_segments")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /advance/i })).not.toBeInTheDocument();
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
