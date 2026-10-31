import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrdersPage from "./page";

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

describe("staff packing queue", () => {
  beforeEach(() => {
    replace.mockReset();
    window.history.replaceState(null, "", "/admin/orders?work=packing");
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read", "fulfillment.pack"],
      };
      if (path.startsWith("admin/orders?")) return [];
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("opens the exact filtered queue and can return to all orders", async () => {
    render(<OrdersPage />);

    expect(await screen.findByText("Showing delivery orders with units still eligible to pack."))
      .toBeInTheDocument();
    expect(screen.getByLabelText("State")).toHaveValue("PROCESSING");
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      "admin/orders?limit=50&offset=0&state=PROCESSING&packing_only=true"
    ));

    await userEvent.setup().click(screen.getByRole("button", { name: "Show all orders" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/orders?limit=50&offset=0"));
    expect(screen.queryByText("Showing delivery orders with units still eligible to pack."))
      .not.toBeInTheDocument();
  });

  it("discards an older filtered search after a newer order search completes", async () => {
    const summary = {
      id: "order-2", number: "MC-20261025-0002", source: "STOREFRONT", state: "PENDING_CONFIRMATION",
      payment_state: "PENDING", payment_method: "COD", fulfillment_method: "DELIVERY",
      customer_name: "Buyer Two", customer_phone: "03000000002", total_minor: 10000,
      currency: "PKR", created_at: "2026-10-25T10:00:00Z",
    };
    let resolvePacking!: (value: Array<typeof summary>) => void;
    const packingResult = new Promise<Array<typeof summary>>((resolve) => { resolvePacking = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read", "fulfillment.pack"],
      });
      if (path === "admin/orders?limit=50&offset=0&state=PROCESSING&packing_only=true") return packingResult;
      if (path === "admin/orders?limit=50&offset=0") return Promise.resolve([summary]);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<OrdersPage />);

    await user.click(await screen.findByRole("button", { name: "Show all orders" }));
    expect(await screen.findByRole("button", { name: /MC-20261025-0002/ })).toBeInTheDocument();
    resolvePacking([]);

    await waitFor(() => expect(screen.getByRole("button", { name: /MC-20261025-0002/ })).toBeInTheDocument());
    expect(screen.queryByText("No matching orders.")).not.toBeInTheDocument();
  });

  it("does not render payment or refund records for order readers without financial permissions", async () => {
    window.history.replaceState(null, "", "/admin/orders");
    const summary = {
      id: "order-1", number: "MC-20261025-0001", source: "STOREFRONT", state: "CONFIRMED",
      payment_state: "PENDING", payment_method: "COD", fulfillment_method: "DELIVERY",
      customer_name: "Buyer", customer_phone: "03000000000", total_minor: 10000,
      currency: "PKR", created_at: "2026-10-25T10:00:00Z",
    };
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read"],
      };
      if (path.startsWith("admin/orders?")) return [summary];
      if (path === "admin/orders/order-1") return {
        ...summary, customer_id: "customer-1", customer_email: "private@example.test",
        address: { line1: null, line2: null, area: null, city: null, postal_code: null, country_code: "PK", delivery_notes: null },
        subtotal_minor: 10000, discount_minor: 0, shipping_charge_minor: 0, policy_version_id: null,
        attribution: { source: null, campaign: null, creator_code: null },
        items: [], events: [],
        payments: [{ id: "payment-1", provider: "provider", method: "COD", attempt_number: 1, amount_minor: 10000, currency: "PKR", status: "PENDING", provider_txn_id: "private-payment-ref", events: [] }],
        shipments: [], pickups: [], returns: [],
        refunds: [{ id: "refund-1", amount_minor: 100, state: "PENDING", reason: "private reason", provider_reference: "private-refund-ref" }],
      };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<OrdersPage />);

    await userEvent.setup().click(await screen.findByRole("button", { name: /MC-20261025-0001/ }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/orders/order-1"));
    expect(screen.queryByRole("heading", { name: "Payments" })).not.toBeInTheDocument();
    expect(screen.queryByText(/private-payment-ref|private-refund-ref|private@example\.test|Refund ·/)).not.toBeInTheDocument();
  });
});

describe("staff stock reservation exception queue", () => {
  beforeEach(() => {
    replace.mockReset();
    window.history.replaceState(null, "", "/admin/orders?work=stock-exceptions");
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read"],
      };
      if (path.startsWith("admin/orders?")) return [];
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("opens the filtered stock exception queue and can return to all orders", async () => {
    render(<OrdersPage />);

    expect(await screen.findByText("Showing COD orders awaiting confirmation or fulfillment orders with outstanding units that lack active stock reservations."))
      .toBeInTheDocument();
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      "admin/orders?limit=50&offset=0&stock_exception_only=true"
    ));

    await userEvent.setup().click(screen.getByRole("button", { name: "Show all orders" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/orders?limit=50&offset=0"));
    expect(screen.queryByText("Showing COD orders awaiting confirmation or fulfillment orders with outstanding units that lack active stock reservations."))
      .not.toBeInTheDocument();
  });
});

describe("confirmed order reservation guard", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/admin/orders");
    const summary = {
      id: "order-1", number: "MC-20261025-0001", source: "STOREFRONT", state: "CONFIRMED",
      payment_state: "PENDING", payment_method: "COD", fulfillment_method: "DELIVERY",
      customer_name: "Buyer", customer_phone: "03000000000", total_minor: 10000,
      currency: "PKR", created_at: "2026-10-25T10:00:00Z",
    };
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "warehouse@example.test", name: "Warehouse", totp_enabled: true,
        permission_keys: ["order.read", "fulfillment.pack"],
      };
      if (path.startsWith("admin/orders?")) return [summary];
      if (path === "admin/orders/order-1") return {
        ...summary, stock_reservation_exception: true,
        customer_id: null, customer_email: null,
        address: { line1: null, line2: null, area: null, city: null, postal_code: null, country_code: "PK", delivery_notes: null },
        subtotal_minor: 10000, discount_minor: 0, shipping_charge_minor: 0, policy_version_id: null,
        attribution: { source: null, campaign: null, creator_code: null },
        items: [{ id: "item-1", sku: "SKU-1", product_title: "Scarf", variant_name: "Rose", quantity: 1, fulfilled_quantity: 0, unit_price_minor: 10000, sale_price_minor: null, discount_allocated_minor: 0, line_total_minor: 10000 }],
        events: [], payments: [], shipments: [], pickups: [], returns: [], refunds: [],
      };
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("displays the stock exception and blocks starting processing", async () => {
    render(<OrdersPage />);

    await userEvent.setup().click(await screen.findByRole("button", { name: /MC-20261025-0001/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live stock reservations do not cover this order. Processing and fulfillment actions are blocked until the stock exception is resolved."
    );
    expect(screen.getByRole("button", { name: "Start processing" })).toBeDisabled();
  });
});

describe("order detail request ordering", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/admin/orders");
  });

  it("keeps the latest selected order when an earlier detail request resolves last", async () => {
    const firstOrder = {
      id: "order-1", number: "MC-20261025-0001", source: "STOREFRONT", state: "CONFIRMED",
      payment_state: "PENDING", payment_method: "COD", fulfillment_method: "DELIVERY",
      customer_name: "Buyer One", customer_phone: "03000000001", total_minor: 10000,
      currency: "PKR", created_at: "2026-10-25T10:00:00Z",
    };
    const secondOrder = { ...firstOrder, id: "order-2", number: "MC-20261025-0002", customer_name: "Buyer Two" };
    let resolveFirst!: (value: Record<string, unknown>) => void;
    let resolveSecond!: (value: Record<string, unknown>) => void;
    const firstDetail = new Promise<Record<string, unknown>>((resolve) => { resolveFirst = resolve; });
    const secondDetail = new Promise<Record<string, unknown>>((resolve) => { resolveSecond = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff-1", email: "orders@example.test", name: "Orders", totp_enabled: true,
        permission_keys: ["order.read"],
      });
      if (path.startsWith("admin/orders?")) return Promise.resolve([firstOrder, secondOrder]);
      if (path === "admin/orders/order-1") return firstDetail;
      if (path === "admin/orders/order-2") return secondDetail;
      throw new Error(`Unexpected request: ${path}`);
    });
    const detail = (order: typeof firstOrder) => ({
      ...order, stock_reservation_exception: false, customer_id: null, customer_email: null,
      address: { line1: null, line2: null, area: null, city: null, postal_code: null, country_code: "PK", delivery_notes: null },
      subtotal_minor: 10000, discount_minor: 0, shipping_charge_minor: 0, policy_version_id: null,
      attribution: { source: null, campaign: null, creator_code: null },
      items: [], events: [], payments: [], shipments: [], pickups: [], returns: [], refunds: [],
    });
    const user = userEvent.setup();
    render(<OrdersPage />);

    await user.click(await screen.findByRole("button", { name: /MC-20261025-0001/ }));
    await user.click(screen.getByRole("button", { name: /MC-20261025-0002/ }));
    resolveSecond(detail(secondOrder));
    expect(await screen.findByRole("heading", { name: "MC-20261025-0002" })).toBeInTheDocument();
    resolveFirst(detail(firstOrder));

    await waitFor(() => expect(screen.getByRole("heading", { name: "MC-20261025-0002" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "MC-20261025-0001" })).not.toBeInTheDocument();
  });
});
