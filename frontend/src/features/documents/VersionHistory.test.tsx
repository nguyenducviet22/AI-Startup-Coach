import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StartupDocument } from "../../api/documents";
import { VersionHistory } from "./VersionHistory";

const baseDocument: StartupDocument = {
  id: "doc-1",
  startup_id: "startup-1",
  doc_type: "lean_canvas",
  version: 2,
  is_current: true,
  created_at: "2026-07-31T10:00:00Z",
  content: {}
};

describe("VersionHistory", () => {
  it("renders versions with current status", () => {
    render(
      <VersionHistory
        documents={[
          baseDocument,
          { ...baseDocument, id: "doc-0", version: 1, is_current: false, created_at: "2026-07-30T10:00:00Z" }
        ]}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByRole("heading", { name: "Version History" })).toBeInTheDocument();
    expect(screen.getByText("Version 2 current")).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
  });

  it("renders an empty state when no versions exist", () => {
    render(<VersionHistory documents={[]} isLoading={false} error={null} />);

    expect(screen.getByText("No versions yet.")).toBeInTheDocument();
  });
});
