import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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

    expect(screen.getByRole("heading", { name: "Lịch sử phiên bản" })).toBeInTheDocument();
    expect(screen.getByText("Phiên bản 2 · hiện tại")).toBeInTheDocument();
    expect(screen.getByText("Phiên bản 1")).toBeInTheDocument();
  });

  it("renders an empty state when no versions exist", () => {
    render(<VersionHistory documents={[]} isLoading={false} error={null} />);

    expect(screen.getByText("Chưa có phiên bản trước.")).toBeInTheDocument();
  });

  it("lets the user preview, compare, and restore an older version", async () => {
    const user = userEvent.setup();
    const oldDocument = { ...baseDocument, id: "doc-0", version: 1, is_current: false };
    const onPreview = vi.fn();
    const onCompare = vi.fn();
    const onRestore = vi.fn();
    render(
      <VersionHistory
        documents={[baseDocument, oldDocument]}
        isLoading={false}
        error={null}
        onPreview={onPreview}
        onCompare={onCompare}
        onRestore={onRestore}
      />
    );

    await user.click(screen.getByRole("button", { name: "Xem phiên bản 1" }));
    await user.click(screen.getByRole("button", { name: "So sánh phiên bản 1" }));
    await user.click(screen.getByRole("button", { name: "Khôi phục phiên bản 1" }));

    expect(onPreview).toHaveBeenCalledWith(oldDocument);
    expect(onCompare).toHaveBeenCalledWith(oldDocument);
    expect(onRestore).toHaveBeenCalledWith(oldDocument);
  });
});
