import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StageControls } from "./StageControls";

describe("StageControls", () => {
  it("does not render an advance-stage action when the current stage is completed", () => {
    render(
      <StageControls
        currentStage="completed"
        onAdvanceStage={vi.fn()}
        onSetStage={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { name: "Journey completed" })).toBeInTheDocument();
    expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /continue/i })).not.toBeInTheDocument();
  });
});
