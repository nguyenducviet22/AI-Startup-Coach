import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PitchDeckView } from "./PitchDeckView";

describe("PitchDeckView", () => {
  it("navigates slides with controls and arrow keys without crossing boundaries", async () => {
    const user = userEvent.setup();
    render(<PitchDeckView startupId="startup-1" startupName="EcoLearn" slides={[{ slide_title: "Vấn đề", content: "Problem" }, { slide_title: "Giải pháp", content: "Solution" }]} />);

    expect(screen.getByRole("heading", { name: "Vấn đề" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Slide tiếp" }));
    expect(screen.getByRole("heading", { name: "Giải pháp" })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("2/2")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("heading", { name: "Vấn đề" })).toBeInTheDocument();
  });

  it("shows an empty state when there are no slides", () => {
    render(<PitchDeckView startupId="startup-1" startupName="EcoLearn" slides={[]} />);
    expect(screen.getByText("Chưa có Pitch outline")).toBeInTheDocument();
  });
});
