import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ManualOrderPage from "./page";

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
vi.mock("@/lib/staff-client", () => ({
  staffJson,
  jsonBody: (value: object) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) }),
}));

const owner = {
  id: "owner-1", email: "owner@example.test", name: "Owner", totp_enabled: true,
  permission_keys: ["order.create_manual"],
};
const orderResult = {
  order_id: "order-1", order_number: "MC-0001", source: "SOCIAL", state: "PENDING_CONFIRMATION",
  total_minor: 125000, replayed: false,
};

describe("manual order entry", () => {
  beforeEach(() => {
    replace.mockReset();
    let createCount = 0;
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return owner;
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") {
        return { items: [{ id: "product-1", title: "Sage dress", status: "PUBLISHED" }] };
      }
      if (path === "admin/orders/manual/options") {
        return { delivery_cities: ["Karachi"], pickup_cities: [], delivery_fee_minor: 25000, payment_methods: ["COD"] };
      }
      if (path === "admin/catalog/products/product-1") {
        return { id: "product-1", title: "Sage dress", status: "PUBLISHED", variants: [{
          id: "variant-1", sku: "SAGE-S", color_name: "Sage", price_minor: 100000,
          sale_price_minor: null, is_active: true,
        }] };
      }
      if (path === "admin/orders/manual" && init?.method === "POST") {
        createCount += 1;
        if (createCount === 1) throw new TypeError("Failed to fetch");
        return { ...orderResult, replayed: true };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("reuses the idempotency key after an interrupted order request", async () => {
    const user = userEvent.setup();
    render(<ManualOrderPage />);

    await user.selectOptions(await screen.findByLabelText("Product"), "product-1");
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/catalog/products/product-1"));
    await user.selectOptions(screen.getByLabelText("Variant"), "variant-1");
    await user.click(screen.getByRole("button", { name: "Add item" }));
    await user.type(screen.getByLabelText("Customer name"), "Rida Buyer");
    await user.type(screen.getByLabelText("Phone"), "+923001234567");
    await user.selectOptions(screen.getByLabelText("City"), "Karachi");
    await user.type(screen.getByLabelText("Delivery address"), "1 Example Road");

    await user.click(screen.getByRole("button", { name: "Record order" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("may have been accepted");
    await user.clear(screen.getByLabelText("Customer name"));
    await user.type(screen.getByLabelText("Customer name"), "Changed Buyer");
    await user.click(screen.getByRole("button", { name: "Record order" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("may have been accepted");
    expect(staffJson.mock.calls.filter(([path]) => path === "admin/orders/manual")).toHaveLength(1);

    await user.clear(screen.getByLabelText("Customer name"));
    await user.type(screen.getByLabelText("Customer name"), "Rida Buyer");
    await user.click(screen.getByRole("button", { name: "Record order" }));

    expect(await screen.findByRole("status")).toHaveTextContent("MC-0001");
    const requests = staffJson.mock.calls.filter(([path, init]) => path === "admin/orders/manual" && init?.method === "POST");
    expect(requests).toHaveLength(2);
    const firstBody = JSON.parse(requests[0][1].body as string) as Record<string, unknown> & { idempotency_key: string };
    const retryBody = JSON.parse(requests[1][1].body as string) as Record<string, unknown> & { idempotency_key: string };
    expect(firstBody.idempotency_key).toHaveLength(36);
    expect(retryBody.idempotency_key).toBe(firstBody.idempotency_key);
    expect({ ...retryBody, idempotency_key: firstBody.idempotency_key }).toEqual(firstBody);
  });

  it("loads and selects a product from the next catalog page", async () => {
    const user = userEvent.setup();
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return owner;
      if (path === "admin/orders/manual/options") {
        return { delivery_cities: ["Karachi"], pickup_cities: [], delivery_fee_minor: 25000, payment_methods: ["COD"] };
      }
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") {
        return { items: [{ id: "product-1", title: "First product", status: "PUBLISHED" }], next_cursor: "cursor-100" };
      }
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED&after=cursor-100") {
        return { items: [{ id: "product-101", title: "Later product", status: "PUBLISHED" }], next_cursor: null };
      }
      if (path === "admin/catalog/products/product-101") {
        return { id: "product-101", title: "Later product", status: "PUBLISHED", variants: [] };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<ManualOrderPage />);
    await screen.findByLabelText("Product");
    await user.click(screen.getByRole("button", { name: "Load more products" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      "admin/catalog/products?limit=100&status=PUBLISHED&after=cursor-100",
    ));
    await screen.findByRole("option", { name: "Later product" });
    await user.selectOptions(screen.getByLabelText("Product"), "product-101");
    expect(await screen.findByLabelText("Variant")).toBeInTheDocument();
    expect(screen.getByLabelText("Product")).toHaveValue("product-101");
  });

  it("shows a staff API outage without sending the user to sign-in", async () => {
    const serviceError = Object.assign(new Error("Staff service unavailable."), { status: 503 });
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") throw serviceError;
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") return { items: [], next_cursor: null };
      if (path === "admin/orders/manual/options") return { delivery_cities: [], pickup_cities: [], delivery_fee_minor: null, payment_methods: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<ManualOrderPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Staff service unavailable.");
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });
});
