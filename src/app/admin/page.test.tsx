import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminHome from "./page";

const { staffJson, replace } = vi.hoisted(() => ({ staffJson: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody: vi.fn() }));

describe("staff actionable dashboard queues", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "staff@example.test", name: "Staff", totp_enabled: true,
        permission_keys: ["dashboard.read", "order.read", "review.moderate", "inventory.read", "fulfillment.pack", "promotion.read"],
      };
      if (path === "admin/analytics/dashboard") return {
        as_of: "2026-10-25T10:00:00Z",
        order_states: { PENDING_CONFIRMATION: 3, CONFIRMED: 0, PROCESSING: 0, FULFILLED: 0, COMPLETED: 0, CANCELLED: 0 },
        queues: { cod_confirmation: 2, packing: 3, stock_reservation_exceptions: 1, product_reviews: 4, zero_available_inventory: 6, low_stock_inventory: 5 },
      };
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("links permissioned current queue counts to their filtered screens", async () => {
    render(<AdminHome />);

    expect(await screen.findByText("COD awaiting confirmation")).toBeInTheDocument();
    expect(screen.getByText("Reviews awaiting moderation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /COD awaiting confirmation 2 Open queue/ })).toHaveAttribute("href", "/admin/orders/cod");
    expect(screen.getByRole("link", { name: /Reviews awaiting moderation 4 Open queue/ })).toHaveAttribute("href", "/admin/reviews");
    expect(screen.getByRole("link", { name: /Delivery orders ready for packing 3 Open packing queue/ }))
      .toHaveAttribute("href", "/admin/orders?work=packing");
    expect(screen.getByRole("link", { name: /Orders with stock reservation exceptions 1 Open stock exception queue/ }))
      .toHaveAttribute("href", "/admin/orders?work=stock-exceptions");
    expect(screen.getByRole("link", { name: /Balances with no available units 6 Open inventory queue/ }))
      .toHaveAttribute("href", "/admin/inventory?availability=zero");
    expect(screen.getByRole("link", { name: /Below configured stock threshold 5 Open low-stock queue/ }))
      .toHaveAttribute("href", "/admin/inventory?availability=low");
    expect(screen.getByRole("link", { name: /Promotions/ })).toHaveAttribute("href", "/admin/promotions");
    expect(screen.queryByText(/Operational queues are still being connected/)).not.toBeInTheDocument();
  });

  it.each([
    {
      role: "owner",
      permissions: ["dashboard.read", "catalog.read", "catalog.write", "catalog.archive", "inventory.read", "inventory.adjust", "inventory.receive", "inventory.inspect", "inventory.thresholds.manage", "order.read", "order.create_manual", "order.confirm", "order.cancel", "fulfillment.pack", "fulfillment.book", "fulfillment.handoff", "customer.read", "customer.manage", "customer.export", "payment.read", "refund.request", "refund.approve", "settlement.read", "settlement.import", "settlement.reconcile", "promotion.read", "promotion.write", "review.moderate", "staff.manage", "settings.manage", "audit.read", "notification.read", "analytics.read"],
      links: ["/admin/orders/cod", "/admin/orders", "/admin/orders/new", "/admin/customers", "/admin/reviews", "/admin/notifications", "/admin/catalog", "/admin/inventory", "/admin/analytics/attribution", "/admin/settings", "/admin/promotions"],
    },
    {
      role: "order_manager",
      permissions: ["dashboard.read", "catalog.read", "order.read", "order.create_manual", "order.confirm", "order.cancel", "fulfillment.pack", "fulfillment.book", "fulfillment.handoff", "customer.read", "payment.read", "refund.request", "review.moderate", "notification.read", "analytics.read"],
      links: ["/admin/orders/cod", "/admin/orders", "/admin/orders/new", "/admin/customers", "/admin/reviews", "/admin/notifications", "/admin/catalog", "/admin/analytics/attribution"],
    },
    {
      role: "warehouse",
      permissions: ["dashboard.read", "inventory.read", "inventory.adjust", "inventory.receive", "inventory.inspect", "inventory.thresholds.manage", "order.read", "fulfillment.pack", "fulfillment.book", "fulfillment.handoff"],
      links: ["/admin/orders/cod", "/admin/orders", "/admin/inventory"],
    },
    {
      role: "customer_support",
      permissions: ["dashboard.read", "order.read", "customer.read", "customer.manage", "refund.request", "review.moderate", "notification.read"],
      links: ["/admin/orders/cod", "/admin/orders", "/admin/customers", "/admin/reviews", "/admin/notifications"],
    },
    {
      role: "marketing",
      permissions: ["dashboard.read", "catalog.read", "promotion.read", "promotion.write", "review.moderate", "analytics.read"],
      links: ["/admin/reviews", "/admin/catalog", "/admin/analytics/attribution", "/admin/promotions"],
    },
  ])("shows only the seeded workspace links for $role", async ({ role, permissions, links }) => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: `staff-${role}`, email: `${role}@example.test`, name: role, totp_enabled: true, permission_keys: permissions,
      };
      if (path === "admin/analytics/dashboard") return {
        as_of: "2026-10-25T10:00:00Z",
        order_states: { PENDING_CONFIRMATION: 0, CONFIRMED: 0, PROCESSING: 0, FULFILLED: 0, COMPLETED: 0, CANCELLED: 0 },
        queues: {},
      };
      if (path === "admin/staff") return [];
      throw new Error(`Unexpected request: ${path}`);
    });

    const { container } = render(<AdminHome />);

    expect(await screen.findByRole("heading", { name: `Welcome, ${role}` })).toBeInTheDocument();
    const actualLinks = new Set(Array.from(container.querySelectorAll("a[href]")).map((link) => link.getAttribute("href")));
    const staffWorkspaces = [
      "/admin/orders/cod", "/admin/orders", "/admin/orders/new", "/admin/customers", "/admin/reviews",
      "/admin/catalog", "/admin/inventory", "/admin/analytics/attribution", "/admin/settings", "/admin/promotions", "/admin/notifications",
    ];
    for (const href of staffWorkspaces) expect(actualLinks.has(href)).toBe(links.includes(href));
    expect(Boolean(screen.queryByRole("heading", { name: "Invite staff" }))).toBe(permissions.includes("staff.manage"));
  });
});
