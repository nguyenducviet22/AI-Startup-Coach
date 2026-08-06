import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PitchDeckView } from "./PitchDeckView";

describe("PitchDeckView", () => {
  it("navigates slides with controls and arrow keys without crossing boundaries", async () => {
    const user = userEvent.setup();
    render(<PitchDeckView startupId="startup-1" startupName="EcoLearn" slides={[{ slide_title: "Problem", content: "Problem" }, { slide_title: "Solution", content: "Solution" }]} />);

    expect(screen.getByRole("heading", { name: "Problem" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next slide" }));
    expect(screen.getByRole("heading", { name: "Solution" })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("2/2")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("heading", { name: "Problem" })).toBeInTheDocument();
  });

  it("shows an empty state when there are no slides", () => {
    render(<PitchDeckView startupId="startup-1" startupName="EcoLearn" slides={[]} />);
    expect(screen.getByText("No pitch outline yet")).toBeInTheDocument();
  });
});
