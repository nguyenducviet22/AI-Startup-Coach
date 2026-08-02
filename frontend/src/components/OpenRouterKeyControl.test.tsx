import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { getStoredOpenRouterApiKey, setStoredOpenRouterApiKey } from "../api/client";
import { OpenRouterKeyControl } from "./OpenRouterKeyControl";

describe("OpenRouterKeyControl", () => {
  afterEach(() => setStoredOpenRouterApiKey(null));

  it("opens beside the account, masks the key, and saves it for the browser session", async () => {
    const user = userEvent.setup();
    render(<OpenRouterKeyControl />);

    await user.click(screen.getByRole("button", { name: "Thêm OpenRouter API key" }));
    const input = screen.getByLabelText("OpenRouter API key");
    expect(input).toHaveAttribute("type", "password");

    await user.type(input, "  sk-or-v1-user-key  ");
    await user.click(screen.getByRole("button", { name: "Hiện API key" }));
    expect(input).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "Lưu key" }));

    expect(getStoredOpenRouterApiKey()).toBe("sk-or-v1-user-key");
    expect(screen.getByRole("button", { name: "OpenRouter API key đã được cấu hình" })).toBeInTheDocument();
  });

  it("removes a previously configured key", async () => {
    setStoredOpenRouterApiKey("sk-existing");
    const user = userEvent.setup();
    render(<OpenRouterKeyControl />);

    await user.click(screen.getByRole("button", { name: "OpenRouter API key đã được cấu hình" }));
    await user.click(screen.getByRole("button", { name: "Xóa key" }));

    expect(getStoredOpenRouterApiKey()).toBeNull();
    expect(screen.getByRole("button", { name: "Thêm OpenRouter API key" })).toBeInTheDocument();
  });
});
