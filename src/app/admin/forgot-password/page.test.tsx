import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForgotPasswordPage from "./page";

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

describe("staff password recovery request", () => {
  beforeEach(() => {
    staffJson.mockReset();
    jsonBody.mockClear();
  });

  it("shows the same neutral confirmation after an accepted request", async () => {
    const user = userEvent.setup();
    staffJson.mockResolvedValue(undefined);
    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.click(screen.getByRole("button", { name: "Send reset instructions" }));

    expect(jsonBody).toHaveBeenCalledWith({ email: "owner@example.test" });
    expect(staffJson).toHaveBeenCalledWith("auth/password/forgot", expect.anything());
    expect(await screen.findByText(/If this account exists, reset instructions will be sent/)).toBeInTheDocument();
  });

  it("keeps service failures visible and retryable", async () => {
    const user = userEvent.setup();
    staffJson.mockRejectedValue(new Error("Recovery service unavailable."));
    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.click(screen.getByRole("button", { name: "Send reset instructions" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Recovery service unavailable.");
    expect(screen.getByRole("button", { name: "Send reset instructions" })).toBeEnabled();
  });
});
