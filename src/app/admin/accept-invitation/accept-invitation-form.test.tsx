import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AcceptInvitationForm } from "./accept-invitation-form";

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

describe("staff invitation acceptance", () => {
  beforeEach(() => {
    staffJson.mockReset();
    jsonBody.mockClear();
  });

  it("submits the invitation token and password, then offers sign-in", async () => {
    const user = userEvent.setup();
    staffJson.mockResolvedValue(undefined);
    render(<AcceptInvitationForm token="invitation-secret" />);

    await user.type(screen.getByLabelText("Name"), "Store Owner");
    await user.type(screen.getByLabelText(/^Password/), "a secure staff password");
    await user.type(screen.getByLabelText("Confirm password"), "a secure staff password");
    await user.click(screen.getByRole("button", { name: "Activate account" }));

    expect(jsonBody).toHaveBeenCalledWith({
      token: "invitation-secret",
      password: "a secure staff password",
      display_name: "Store Owner",
    });
    expect(staffJson).toHaveBeenCalledWith("auth/accept-invitation", expect.anything());
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/admin/login");
  });

  it("keeps mismatched passwords local and shows API failures", async () => {
    const user = userEvent.setup();
    render(<AcceptInvitationForm token="invitation-secret" />);
    await user.type(screen.getByLabelText("Name"), "Store Owner");
    await user.type(screen.getByLabelText(/^Password/), "a secure staff password");
    await user.type(screen.getByLabelText("Confirm password"), "a different staff password");
    await user.click(screen.getByRole("button", { name: "Activate account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(staffJson).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Confirm password"));
    await user.type(screen.getByLabelText("Confirm password"), "a secure staff password");
    staffJson.mockRejectedValue(new Error("Invitation expired."));
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invitation expired.");
  });
});
