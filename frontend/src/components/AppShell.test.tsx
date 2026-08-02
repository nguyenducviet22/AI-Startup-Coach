import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Startup } from "../api/startups";
import { sortStartupsByRecent, StartupList, StartupNameControl } from "./AppShell";

const STARTUPS: Startup[] = [
  startup("1", "EcoLearn", "idea"),
  startup("2", "Đổi mới xanh", "swot"),
  startup("3", "TutorOS", "lean_canvas"),
  startup("4", "Pitch Ready", "completed")
];

describe("StartupList", () => {
  it("searches without accents and reports the visible result count", async () => {
    render(<StartupList startups={STARTUPS} selectedStartupId="1" isLoading={false} error={null} onSelect={vi.fn()} />);

    expect(screen.getByText("4/4 startup")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "Tìm startup" }), "doi moi");

    expect(screen.getByText("Đổi mới xanh")).toBeInTheDocument();
    expect(screen.queryByText("EcoLearn")).not.toBeInTheDocument();
    expect(screen.getByText("1/4 startup")).toBeInTheDocument();
  });

  it("filters active and completed startups with a contextual empty state", async () => {
    render(<StartupList startups={STARTUPS} selectedStartupId="1" isLoading={false} error={null} onSelect={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Hoàn thành" }));
    expect(screen.getByText("Pitch Ready")).toBeInTheDocument();
    expect(screen.getByText("1/4 startup")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox", { name: "Tìm startup" }), "không tồn tại");
    expect(screen.getByText("Không tìm thấy startup phù hợp")).toBeInTheDocument();
  });
});

describe("sortStartupsByRecent", () => {
  it("keeps the most recently updated startup first and undated startups last", () => {
    const older = { ...startup("1", "Older", "idea"), updated_at: "2026-01-01T00:00:00Z" };
    const newer = { ...startup("2", "Newer", "swot"), updated_at: "2026-07-01T00:00:00Z" };
    const undated = startup("3", "Undated", "lean_canvas");

    expect(sortStartupsByRecent([older, undated, newer]).map((item) => item.id)).toEqual(["2", "1", "3"]);
  });
});

describe("StartupNameControl", () => {
  it("opens rename from the right-click menu without showing an adjacent action", async () => {
    const onRename = vi.fn();
    render(<StartupNameControl name="Paperpeer" isRenaming={false} onRename={onRename} />);

    expect(screen.queryByRole("button", { name: "Đổi tên" })).not.toBeInTheDocument();
    fireEvent.contextMenu(screen.getByRole("heading", { name: "Paperpeer" }), { clientX: 80, clientY: 90 });
    await userEvent.click(screen.getByRole("menuitem", { name: "Đổi tên startup" }));
    const input = screen.getByRole("textbox", { name: "Tên startup" });
    await userEvent.clear(input);
    await userEvent.type(input, "Paperpeer mới");
    await userEvent.click(screen.getByRole("button", { name: "Lưu" }));

    expect(onRename).toHaveBeenCalledWith("Paperpeer mới");
  });
});

function startup(id: string, name: string, current_stage: Startup["current_stage"]): Startup {
  return { id, user_id: "local-user", name, current_stage, created_at: null, updated_at: null };
}
