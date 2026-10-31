import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InventoryAdminPage from "./page";

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

const balance = (sku: string, low_stock_threshold: number | null = null) => ({
  variant_id: `variant-${sku}`, location_id: "location-1", product_title: `Product ${sku}`,
  sku, color_name: "Rose", location_name: "Warehouse", location_key: "main",
  on_hand: 0, reserved: 0, available: 0, low_stock_threshold,
});

describe("inventory availability queue", () => {
  beforeEach(() => {
    replace.mockReset();
    window.history.replaceState(null, "", "/admin/inventory?availability=zero");
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["inventory.read"],
      };
      if (path === "admin/inventory/locations") return [];
      if (path === "admin/inventory/variants") return [];
      if (path === "admin/inventory/out-of-stock?limit=100&offset=0") {
        return { items: [balance("SKU-1")], total_count: 2, limit: 100, offset: 0 };
      }
      if (path === "admin/inventory/out-of-stock?limit=100&offset=1") {
        return { items: [balance("SKU-2")], total_count: 2, limit: 100, offset: 1 };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("loads the filtered queue from the URL and appends the next page", async () => {
    render(<InventoryAdminPage />);

    expect(await screen.findByRole("heading", { name: "Balances with no available units" })).toBeInTheDocument();
    expect(await screen.findByText("SKU-1")).toBeInTheDocument();
    expect(staffJson).toHaveBeenCalledWith("admin/inventory/out-of-stock?limit=100&offset=0");

    await userEvent.setup().click(screen.getByRole("button", { name: "Load more unavailable balances" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      "admin/inventory/out-of-stock?limit=100&offset=1"
    ));
    expect(await screen.findByText("SKU-2")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Showing 2 of 2/)).toBeInTheDocument());
  });

  it("loads the configured low-stock queue from the dashboard link", async () => {
    window.history.replaceState(null, "", "/admin/inventory?availability=low");
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["inventory.read"],
      };
      if (path === "admin/inventory/locations" || path === "admin/inventory/variants") return [];
      if (path === "admin/inventory/low-stock?limit=100&offset=0") {
        return { items: [balance("SKU-LOW", 4)], total_count: 1, limit: 100, offset: 0 };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<InventoryAdminPage />);

    expect(await screen.findByRole("heading", { name: "Below configured stock threshold" })).toBeInTheDocument();
    expect(await screen.findByText("SKU-LOW")).toBeInTheDocument();
    expect(await screen.findByText("4", { selector: "td" })).toBeInTheDocument();
  });

  it("discards a queued page response after switching availability filters", async () => {
    let resolveOldPage!: (value: { items: ReturnType<typeof balance>[]; total_count: number; limit: number; offset: number }) => void;
    const oldPage = new Promise<{ items: ReturnType<typeof balance>[]; total_count: number; limit: number; offset: number }>((resolve) => { resolveOldPage = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["inventory.read"],
      });
      if (path === "admin/inventory/locations" || path === "admin/inventory/variants") return Promise.resolve([]);
      if (path === "admin/inventory/out-of-stock?limit=100&offset=0") {
        return Promise.resolve({ items: [balance("SKU-1")], total_count: 2, limit: 100, offset: 0 });
      }
      if (path === "admin/inventory/out-of-stock?limit=100&offset=1") return oldPage;
      if (path === "admin/inventory/low-stock?limit=100&offset=0") {
        return Promise.resolve({ items: [balance("SKU-LOW", 4)], total_count: 1, limit: 100, offset: 0 });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<InventoryAdminPage />);

    await screen.findByText("SKU-1");
    await user.click(screen.getByRole("button", { name: "Load more unavailable balances" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      "admin/inventory/out-of-stock?limit=100&offset=1"
    ));
    await user.click(screen.getByRole("button", { name: "Below threshold" }));
    expect(await screen.findByText("SKU-LOW")).toBeInTheDocument();
    resolveOldPage({ items: [balance("SKU-2")], total_count: 2, limit: 100, offset: 1 });

    await waitFor(() => expect(screen.queryByText("SKU-2")).not.toBeInTheDocument());
    expect(screen.getByText("SKU-LOW")).toBeInTheDocument();
  });

  it("lets authorized warehouse staff configure a threshold for a balance", async () => {
    window.history.replaceState(null, "", "/admin/inventory");
    let threshold = 3;
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["inventory.read", "inventory.thresholds.manage"],
      };
      if (path === "admin/inventory/locations") return [{ id: "location-1", key: "main", name: "Warehouse" }];
      if (path === "admin/inventory/variants") return [{ id: "variant-SKU-1", product_title: "Product SKU-1", sku: "SKU-1", color_name: "Rose" }];
      if (path === "admin/inventory/balances?limit=500") return [{ ...balance("SKU-1", threshold), on_hand: 6, available: 6 }];
      if (path === "admin/inventory/thresholds") {
        expect(init?.method).toBe("PATCH");
        threshold = 5;
        return { variant_id: "variant-SKU-1", location_id: "location-1", low_stock_threshold: threshold };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<InventoryAdminPage />);

    await user.click(await screen.findByRole("button", { name: /SKU-1/ }));
    const input = screen.getByLabelText("Alert at or below");
    await user.clear(input);
    await user.type(input, "5");
    await user.click(screen.getByRole("button", { name: "Save alert level" }));

    expect(await screen.findByText("Alert set at 5 available units.")).toBeInTheDocument();
  });

  it("keeps movement history attached to the most recently selected balance", async () => {
    window.history.replaceState(null, "", "/admin/inventory");
    let resolveFirst!: (value: { items: Array<Record<string, unknown>> }) => void;
    let resolveSecond!: (value: { items: Array<Record<string, unknown>> }) => void;
    const firstHistory = new Promise<{ items: Array<Record<string, unknown>> }>((resolve) => { resolveFirst = resolve; });
    const secondHistory = new Promise<{ items: Array<Record<string, unknown>> }>((resolve) => { resolveSecond = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["inventory.read", "inventory.inspect"],
      });
      if (path === "admin/inventory/locations" || path === "admin/inventory/variants") return Promise.resolve([]);
      if (path === "admin/inventory/balances?limit=500") {
        return Promise.resolve([balance("SKU-1"), { ...balance("SKU-2"), variant_id: "variant-SKU-2" }]);
      }
      if (path.includes("variant-SKU-1")) return firstHistory;
      if (path.includes("variant-SKU-2")) return secondHistory;
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<InventoryAdminPage />);

    await user.click(await screen.findByRole("button", { name: /SKU-1/ }));
    await user.click(screen.getByRole("button", { name: /SKU-2/ }));
    resolveSecond({ items: [{
      id: "movement-2", delta_on_hand: 2, delta_reserved: 0, reason: "RECEIVE",
      actor_id: null, notes: null, created_at: "2026-10-25T00:00:00Z",
    }] });
    expect(await screen.findByText("RECEIVE · +2 on hand")).toBeInTheDocument();

    resolveFirst({ items: [{
      id: "movement-1", delta_on_hand: 1, delta_reserved: 0, reason: "RECEIVE",
      actor_id: null, notes: null, created_at: "2026-10-25T00:00:00Z",
    }] });
    await waitFor(() => expect(screen.getByText("RECEIVE · +2 on hand")).toBeInTheDocument());
    expect(screen.getByText("Recent movements · SKU-2")).toBeInTheDocument();
    expect(screen.queryByText("RECEIVE · +1 on hand")).not.toBeInTheDocument();
  });
});
