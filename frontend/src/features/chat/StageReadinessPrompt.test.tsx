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

    await userEvent.click(screen.getByRole("button", { name: "Tiếp tục đến Mô hình kinh doanh" }));

    expect(screen.getByText("Sẵn sàng cho giai đoạn tiếp theo")).toBeInTheDocument();
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

    expect(screen.getByText("Cần thêm thông tin")).toBeInTheDocument();
    expect(screen.getByText("Phân khúc khách hàng")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /tiếp tục/i })).not.toBeInTheDocument();
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
