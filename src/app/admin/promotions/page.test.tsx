import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PromotionsPage from "./page";

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
  jsonBody: (value: object) => ({ method: "POST", body: JSON.stringify(value) }),
}));

const coupon = {
  id: "coupon-1", code: "WELCOME10", type: "PERCENT", value_minor: 10, state: "ACTIVE", is_active: true,
  min_order_minor: null, max_discount_minor: null, usage_limit: null, per_customer_limit: 1,
  starts_at: null, ends_at: null, product_ids: [], category_ids: [],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("promotion access", () => {
  beforeEach(() => {
    replace.mockReset();
  });

  it("shows existing codes to read-only staff without requesting catalog data or exposing write actions", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "staff@example.test", name: "Staff", totp_enabled: true,
        permission_keys: ["promotion.read"],
      };
      if (path === "admin/coupons") return [coupon];
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<PromotionsPage />);

    expect(await screen.findByRole("heading", { name: "WELCOME10" })).toBeInTheDocument();
    expect(screen.getByText("You have read-only access to promotions.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create promotion" })).not.toBeInTheDocument();
    expect(staffJson).toHaveBeenCalledTimes(2);
  });

  it("loads catalog data and exposes editing controls to promotion writers", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "staff@example.test", name: "Staff", totp_enabled: true,
        permission_keys: ["promotion.read", "promotion.write"],
      };
      if (path === "admin/coupons") return [coupon];
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") return { items: [] };
      if (path === "admin/catalog/categories") return { items: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<PromotionsPage />);

    expect(await screen.findByRole("heading", { name: "WELCOME10" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create promotion" })).toBeInTheDocument();
  });

  it("loads later published products for promotion scopes", async () => {
    const user = userEvent.setup();
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "staff@example.test", name: "Staff", totp_enabled: true,
        permission_keys: ["promotion.read", "promotion.write"],
      };
      if (path === "admin/coupons") return [];
      if (path === "admin/catalog/categories") return { items: [] };
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") {
        return { items: [{ id: "product-1", title: "First product", slug: "first", status: "PUBLISHED" }], next_cursor: "cursor-100" };
      }
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED&after=cursor-100") {
        return { items: [{ id: "product-101", title: "Later product", slug: "later", status: "PUBLISHED" }], next_cursor: null };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<PromotionsPage />);
    await screen.findByRole("checkbox", { name: "First product" });
    await user.click(screen.getByRole("button", { name: "Load more products" }));

    expect(await screen.findByRole("checkbox", { name: "Later product" })).toBeInTheDocument();
    expect(staffJson).toHaveBeenCalledWith("admin/catalog/products?limit=100&status=PUBLISHED&after=cursor-100");
  });

  it("locks promotion fields while a create request is in flight", async () => {
    const user = userEvent.setup();
    const save = deferred<typeof coupon>();
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return {
        id: "staff-1", email: "staff@example.test", name: "Staff", totp_enabled: true,
        permission_keys: ["promotion.read", "promotion.write"],
      };
      if (path === "admin/coupons" && init?.method === "POST") return save.promise;
      if (path === "admin/coupons") return [];
      if (path === "admin/catalog/products?limit=100&status=PUBLISHED") return { items: [], next_cursor: null };
      if (path === "admin/catalog/categories") return { items: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<PromotionsPage />);
    const codeInput = await screen.findByLabelText("Code");
    await user.type(codeInput, "LAUNCH10");
    await user.type(screen.getByLabelText("Discount percent"), "10");
    await user.click(screen.getByRole("button", { name: "Create promotion" }));

    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/coupons", expect.objectContaining({ method: "POST" })));
    expect(codeInput).toBeDisabled();
    expect(screen.getByLabelText("Discount percent")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();

    save.resolve({ ...coupon, code: "LAUNCH10" });
    expect(await screen.findByRole("status")).toHaveTextContent("LAUNCH10 created");
  });
});
