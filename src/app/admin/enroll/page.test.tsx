import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EnrollPage from "./page";

const { router, staffJson, jsonBody } = vi.hoisted(() => ({
  router: { replace: vi.fn() },
  staffJson: vi.fn(),
  jsonBody: vi.fn((value: object) => ({ method: "POST", body: JSON.stringify(value) })),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody }));

describe("staff authenticator enrollment", () => {
  beforeEach(() => {
    router.replace.mockReset();
    staffJson.mockReset();
    jsonBody.mockClear();
  });

  it("loads the enrollment secret, verifies a code, and returns to staff home", async () => {
    const user = userEvent.setup();
    staffJson
      .mockResolvedValueOnce({ id: "staff-1", permission_keys: [], totp_enabled: false })
      .mockResolvedValueOnce({ secret: "totp-enrollment-secret" })
      .mockResolvedValueOnce(undefined);
    render(<EnrollPage />);

    await user.click(await screen.findByRole("button", { name: "Start setup" }));
    expect(await screen.findByLabelText("Authenticator setup key")).toHaveTextContent("totp-enrollment-secret");
    await user.type(screen.getByLabelText("Six-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    expect(staffJson).toHaveBeenNthCalledWith(2, "auth/setup-totp", { method: "POST" });
    expect(jsonBody).toHaveBeenCalledWith({ totp_code: "123456" });
    expect(staffJson).toHaveBeenNthCalledWith(3, "auth/verify-totp", expect.anything());
    expect(router.replace).toHaveBeenCalledWith("/admin");
  });

  it("shows enrollment API errors without losing the retry path", async () => {
    const user = userEvent.setup();
    staffJson
      .mockResolvedValueOnce({ id: "staff-1", permission_keys: [], totp_enabled: false })
      .mockRejectedValueOnce(new Error("Enrollment service unavailable."));
    render(<EnrollPage />);

    await user.click(await screen.findByRole("button", { name: "Start setup" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enrollment service unavailable.");
    expect(screen.getByRole("button", { name: "Start setup" })).toBeEnabled();
  });
});
