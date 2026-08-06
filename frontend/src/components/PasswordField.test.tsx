import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { PasswordField } from "./PasswordField";

function PasswordHarness({ showStrength = false }: { showStrength?: boolean }) {
  const [value, setValue] = useState("");
  return <PasswordField value={value} onChange={setValue} autoComplete="new-password" showStrength={showStrength} />;
}

describe("PasswordField", () => {
  it("toggles password visibility without changing the value", async () => {
    const user = userEvent.setup();
    render(<PasswordHarness />);
    const input = screen.getByLabelText("Password");
    await user.type(input, "Secret123");
    expect(input).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("Secret123");
  });

  it("reports the required length and strength", async () => {
    const user = userEvent.setup();
    render(<PasswordHarness showStrength />);
    const input = screen.getByLabelText("Password");
    await user.type(input, "StrongPass123!");
    expect(screen.getByText("Strong")).toBeInTheDocument();
    expect(screen.getByText(/At least 8 characters/)).toHaveClass("requirement-met");
  });
});
