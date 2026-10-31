import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NotificationsAdminPage from "./page";

const { staffJson, replace, router } = vi.hoisted(() => {
  const replace = vi.fn();
  return { staffJson: vi.fn(), replace, router: { replace } };
});

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody: vi.fn() }));

describe("staff email delivery monitor", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockReset();
  });

  it("shows paginated status without recipient or credential data", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "support@example.test", name: "Support", totp_enabled: true,
        permission_keys: ["notification.read"],
      };
      if (path === "admin/notifications/outbox?limit=50&offset=0") return {
        items: [{
          id: "event-1", event_type: "email.send", aggregate_type: "customer_email_otp",
          status: "FAILED", attempts: 10, created_at: "2026-10-25T10:00:00Z",
          processed_at: null, next_attempt_at: null,
        }],
        total_count: 1, limit: 50, offset: 0,
      };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<NotificationsAdminPage />);

    expect(await screen.findByRole("heading", { name: "Email delivery" })).toBeInTheDocument();
    expect(await screen.findByText("customer email otp")).toBeInTheDocument();
    expect(screen.getByText("No automatic retries remain")).toBeInTheDocument();
    expect(screen.queryByText(/recipient|credential|encrypted|token/i, { selector: "td" })).not.toBeInTheDocument();
    expect(staffJson).toHaveBeenCalledWith("admin/notifications/outbox?limit=50&offset=0");
  });

  it("does not request the outbox for staff without notification.read", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read"],
      };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<NotificationsAdminPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Notification access is not included");
    expect(staffJson.mock.calls.some(([path]) => String(path).startsWith("admin/notifications/outbox"))).toBe(false);
  });

  it("locks the status filter while the matching page is loading", async () => {
    let resolvePage!: (value: { items: Array<Record<string, unknown>>; total_count: number; limit: number; offset: number }) => void;
    const pendingPage = new Promise<{ items: Array<Record<string, unknown>>; total_count: number; limit: number; offset: number }>((resolve) => { resolvePage = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff-1", email: "support@example.test", name: "Support", totp_enabled: true,
        permission_keys: ["notification.read"],
      });
      if (path === "admin/notifications/outbox?limit=50&offset=0") return pendingPage;
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<NotificationsAdminPage />);

    const statusFilter = await screen.findByRole("combobox", { name: "Delivery status" });
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/notifications/outbox?limit=50&offset=0"));
    expect(statusFilter).toBeDisabled();
    resolvePage({ items: [], total_count: 0, limit: 50, offset: 0 });
    await screen.findByText("No email events match this status.");
    expect(statusFilter).toBeEnabled();
  });
});
