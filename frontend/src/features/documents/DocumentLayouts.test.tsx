import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeanCanvasLayout, SwotLayout } from "./DocumentLayouts";

describe("DocumentLayouts", () => {
  it("renders Lean Canvas as nine named blocks", () => {
    render(
      <LeanCanvasLayout
        content={{
          problem: "Tutors lose time coordinating lessons.",
          solution: "Shared scheduling workflow.",
          unique_value_proposition: "Less admin, more teaching.",
          customer_segments: "Tutoring centers",
          unfair_advantage: "Existing school partnerships",
          key_metrics: "Lessons scheduled per week",
          channels: "District referrals",
          cost_structure: "Cloud hosting and support",
          revenue_streams: "Monthly subscription"
        }}
      />
    );

    const canvas = screen.getByLabelText("Lean Canvas blocks");
    expect(within(canvas).getAllByRole("heading", { level: 4 })).toHaveLength(9);
    expect(screen.getByRole("heading", { name: "Problem" })).toBeInTheDocument();
    expect(screen.getByText("Tutors lose time coordinating lessons.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Revenue Streams" })).toBeInTheDocument();
    expect(screen.getByText("Monthly subscription")).toBeInTheDocument();
  });

  it("renders SWOT as four grouped lists", () => {
    render(
      <SwotLayout
        content={{
          strengths: ["Teacher relationships", "Simple workflow"],
          weaknesses: ["Small pilot sample"],
          opportunities: ["After-school programs"],
          threats: ["Existing LMS tools"]
        }}
      />
    );

    const swot = screen.getByLabelText("SWOT groups");
    expect(within(swot).getAllByRole("heading", { level: 4 })).toHaveLength(4);
    expect(screen.getByRole("heading", { name: "Strengths" })).toBeInTheDocument();
    expect(screen.getByText("Teacher relationships")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Threats" })).toBeInTheDocument();
    expect(screen.getByText("Existing LMS tools")).toBeInTheDocument();
  });
});
