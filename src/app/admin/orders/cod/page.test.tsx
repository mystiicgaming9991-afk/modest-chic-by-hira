import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodQueuePage from "./page";

const { staffJson } = vi.hoisted(() => ({ staffJson: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody: vi.fn() }));

describe("COD queue reservation exceptions", () => {
  beforeEach(() => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "orders@example.test", name: "Orders", totp_enabled: true,
        permission_keys: ["order.read", "order.confirm"],
      };
      if (path === "admin/orders/cod/pending?limit=100&offset=0") return {
        items: [{
          id: "order-1", number: "MC-20261025-0001", state: "PENDING_CONFIRMATION",
          customer_name: "Buyer", customer_phone: "03000000000", total_minor: 10000,
          fulfillment_method: "DELIVERY", address_city: "Karachi",
          stock_reservation_exception: true,
        }],
        total_count: 1, limit: 100, offset: 0,
      };
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("shows the reservation problem and blocks confirmation", async () => {
    render(<CodQueuePage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live stock reservations do not cover this order. Confirmation is blocked until the stock exception is resolved."
    );
    await userEvent.setup().type(screen.getByLabelText("Contact notes"), "Buyer confirmed by phone");
    expect(screen.getByRole("button", { name: "Confirm order" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Decline order" })).toBeEnabled();
  });
});

describe("COD queue request ordering", () => {
  beforeEach(() => staffJson.mockReset());

  it("discards a pending next-page response after a contact refresh", async () => {
    const order = {
      id: "order-1", number: "MC-20261025-0001", state: "PENDING_CONFIRMATION",
      customer_name: "Buyer", customer_phone: "03000000000", total_minor: 10000,
      fulfillment_method: "DELIVERY", address_city: "Karachi", stock_reservation_exception: false,
    };
    const staleOrder = { ...order, id: "order-stale", number: "MC-20261025-0099" };
    let resolveOldPage!: (value: { items: typeof order[]; total_count: number; limit: number; offset: number }) => void;
    const oldPage = new Promise<{ items: typeof order[]; total_count: number; limit: number; offset: number }>((resolve) => { resolveOldPage = resolve; });
    let firstPageLoads = 0;
    staffJson.mockImplementation(async (path: string | undefined) => {
      if (path === undefined) return {};
      if (path === "auth/me") return {
        id: "staff-1", email: "orders@example.test", name: "Orders", totp_enabled: true,
        permission_keys: ["order.read", "order.confirm"],
      };
      if (path === "admin/orders/cod/pending?limit=100&offset=0") {
        firstPageLoads += 1;
        return { items: [order], total_count: firstPageLoads === 1 ? 2 : 1, limit: 100, offset: 0 };
      }
      if (path === "admin/orders/cod/pending?limit=100&offset=1") return oldPage;
      if (path === "admin/orders/cod/order-1/contact-attempts") return {};
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CodQueuePage />);

    await user.click(await screen.findByRole("button", { name: "Load more orders" }));
    await user.type(await screen.findByLabelText("Contact notes"), "Called the buyer");
    await user.click(screen.getByRole("button", { name: "No answer" }));
    expect(await screen.findByText("Showing 1 of 1 pending COD orders.")).toBeInTheDocument();
    await act(async () => {
      resolveOldPage({ items: [staleOrder], total_count: 2, limit: 100, offset: 1 });
      await oldPage;
    });

    expect(screen.queryByText("MC-20261025-0099")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 1 pending COD orders.")).toBeInTheDocument();
  });
});
