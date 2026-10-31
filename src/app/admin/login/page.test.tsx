import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StaffLoginPage from "./page";

const { replace, staffJson, jsonBody } = vi.hoisted(() => ({
  replace: vi.fn(),
  staffJson: vi.fn(),
  jsonBody: vi.fn((value: object) => ({ method: "POST", body: JSON.stringify(value) })),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody }));

describe("staff sign-in", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockReset();
    jsonBody.mockClear();
  });

  it("submits the credentials and routes an enrolled account to staff home", async () => {
    const user = userEvent.setup();
    staffJson.mockResolvedValue({ auth_state: "ACTIVE" });
    render(<StaffLoginPage />);

    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
    await user.type(screen.getByLabelText(/Authenticator code/), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(jsonBody).toHaveBeenCalledWith({
      email: "owner@example.test",
      password: "correct horse battery staple",
      totp_code: "123456",
    });
    expect(staffJson).toHaveBeenCalledWith("auth/login", expect.objectContaining({ method: "POST" }));
    expect(replace).toHaveBeenCalledWith("/admin");
  });

  it("routes first sign-in into required authenticator enrollment", async () => {
    const user = userEvent.setup();
    staffJson.mockResolvedValue({ auth_state: "TOTP_ENROLLMENT_REQUIRED" });
    render(<StaffLoginPage />);

    await user.type(screen.getByLabelText("Email"), "new-owner@example.test");
    await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(jsonBody).toHaveBeenCalledWith({
      email: "new-owner@example.test",
      password: "correct horse battery staple",
      totp_code: null,
    });
    expect(replace).toHaveBeenCalledWith("/admin/enroll");
  });

  it("shows authentication failures without navigating away", async () => {
    const user = userEvent.setup();
    staffJson.mockRejectedValue(new Error("Sign in failed."));
    render(<StaffLoginPage />);

    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.type(screen.getByLabelText("Password"), "wrong password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in failed.");
    expect(replace).not.toHaveBeenCalled();
  });
});
