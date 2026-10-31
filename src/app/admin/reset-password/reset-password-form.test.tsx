import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordForm } from "./reset-password-form";

const { staffJson, jsonBody } = vi.hoisted(() => ({
  staffJson: vi.fn(),
  jsonBody: vi.fn((value: object) => ({ method: "POST", body: JSON.stringify(value) })),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody }));

describe("staff password reset", () => {
  beforeEach(() => {
    staffJson.mockReset();
    jsonBody.mockClear();
  });

  it("submits the reset token and new password, then links to sign-in", async () => {
    const user = userEvent.setup();
    staffJson.mockResolvedValue(undefined);
    render(<ResetPasswordForm token="reset-secret" />);

    await user.type(screen.getByLabelText("New password"), "a secure staff password");
    await user.type(screen.getByLabelText("Confirm password"), "a secure staff password");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(jsonBody).toHaveBeenCalledWith({ token: "reset-secret", new_password: "a secure staff password" });
    expect(staffJson).toHaveBeenCalledWith("auth/password/reset", expect.anything());
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/admin/login");
  });

  it("rejects mismatched passwords and reports an expired reset token", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm token="reset-secret" />);
    await user.type(screen.getByLabelText("New password"), "a secure staff password");
    await user.type(screen.getByLabelText("Confirm password"), "a different staff password");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(staffJson).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Confirm password"));
    await user.type(screen.getByLabelText("Confirm password"), "a secure staff password");
    staffJson.mockRejectedValue(new Error("Reset link expired."));
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Reset link expired.");
  });
});
