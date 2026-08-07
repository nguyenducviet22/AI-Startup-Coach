import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResearchEvidence } from "./ResearchEvidence";

const research = {
  evidence: [{ source_id: "source-1", url: "https://example.com/source", title: "Official source", excerpt: "The supported evidence.", retrieved_at: "2026-08-07T00:00:00Z", published_at: "2026-08-01T00:00:00Z", authority: "official", legal_or_regulatory: true }],
  cache_hit: true,
  retrieved_at: "2026-08-07T00:00:00Z",
  served_at: "2026-08-07T01:00:00Z",
  legal_notice: "This is legal information, not legal advice."
};

describe("ResearchEvidence", () => {
  it("renders durable source links, metadata, and the legal notice", () => {
    render(<ResearchEvidence research={research} />);

    expect(screen.getByRole("region", { name: "Research evidence" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Official source" })).toHaveAttribute("href", "https://example.com/source");
    expect(screen.getByText("The supported evidence.")).toBeInTheDocument();
    expect(screen.getByText(/Published/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("not legal advice");
  });
});
