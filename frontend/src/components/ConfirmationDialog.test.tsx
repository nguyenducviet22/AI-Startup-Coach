import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmationDialog } from "./ConfirmationDialog";

describe("ConfirmationDialog", () => {
  it("requires an explicit confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmationDialog open title="Chuyển giai đoạn?" description="Kiểm tra trước khi tiếp tục." confirmLabel="Tiếp tục" onConfirm={onConfirm} onCancel={onCancel} />);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tiếp tục" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("closes with Escape", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<ConfirmationDialog open title="Đăng xuất?" description="Xác nhận đăng xuất." confirmLabel="Đăng xuất" onConfirm={vi.fn()} onCancel={onCancel} />);
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
