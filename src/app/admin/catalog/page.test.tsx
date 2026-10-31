import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CatalogAdminPage from "./page";

const { staffJson, replace } = vi.hoisted(() => ({ staffJson: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({
  staffJson,
  jsonBody: (value: object) => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  }),
}));

const productId = "123e4567-e89b-12d3-a456-426614174000";
const product = {
  id: productId,
  slug: "linen-dress",
  title: "Linen dress",
  description: null,
  fabric: null,
  care: null,
  dimensions: null,
  status: "DRAFT" as const,
  created_at: "2026-10-25T10:00:00Z",
  updated_at: "2026-10-25T10:00:00Z",
};

describe("catalog media attachment", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockReset();
  });

  it("attaches existing media metadata without pretending to upload a file", async () => {
    let media: Array<Record<string, unknown>> = [];
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return {
        id: "staff", email: "owner@example.test", name: "Owner", totp_enabled: true,
        permission_keys: ["catalog.read", "catalog.write"],
      };
      if (path.startsWith("admin/catalog/products?")) return { items: [product], next_cursor: null };
      if (path === `admin/catalog/products/${productId}`) return { ...product, variants: [], media };
      if (path === `admin/catalog/products/${productId}/media` && init?.method === "POST") {
        const values = JSON.parse(String(init.body));
        media = [{ id: "media-1", product_id: productId, status: "PUBLISHED", ...values }];
        return media[0];
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const user = userEvent.setup();
    render(<CatalogAdminPage />);
    await user.click(await screen.findByRole("button", { name: /Linen dress/ }));
    await user.type(await screen.findByLabelText("Existing object key"), "products/linen/front.webp");
    await user.type(screen.getByLabelText("Alternative text"), "Front view of a linen dress");
    await user.type(screen.getByLabelText("Width in pixels"), "800");
    await user.type(screen.getByLabelText("Height in pixels"), "1000");
    await user.click(screen.getByLabelText("Set as primary image"));
    await user.click(screen.getByRole("button", { name: "Attach existing media" }));

    expect(await screen.findByText("products/linen/front.webp")).toBeInTheDocument();
    expect(await screen.findByText(/media metadata including the object key is visible in the public catalog API/)).toBeInTheDocument();
    const [path, init] = staffJson.mock.calls.find(([requestPath, request]) => requestPath.endsWith("/media") && request?.method === "POST") ?? [];
    expect(path).toBe(`admin/catalog/products/${productId}/media`);
    expect(JSON.parse(init.body as string)).toEqual({
      object_key: "products/linen/front.webp",
      media_type: "image/webp",
      alt_text: "Front view of a linen dress",
      width: 800,
      height: 1000,
      sort_order: 0,
      is_primary: true,
    });
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(`admin/catalog/products/${productId}`));
  });

  it("keeps details for the latest selected product when requests resolve out of order", async () => {
    const secondProduct = { ...product, id: "223e4567-e89b-12d3-a456-426614174000", title: "Cotton shawl", slug: "cotton-shawl" };
    let resolveFirst!: (value: Record<string, unknown>) => void;
    let resolveSecond!: (value: Record<string, unknown>) => void;
    const firstDetail = new Promise<Record<string, unknown>>((resolve) => { resolveFirst = resolve; });
    const secondDetail = new Promise<Record<string, unknown>>((resolve) => { resolveSecond = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff", email: "owner@example.test", name: "Owner", totp_enabled: true,
        permission_keys: ["catalog.read"],
      });
      if (path.startsWith("admin/catalog/products?")) return Promise.resolve({ items: [product, secondProduct], next_cursor: null });
      if (path === `admin/catalog/products/${productId}`) return firstDetail;
      if (path === `admin/catalog/products/${secondProduct.id}`) return secondDetail;
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CatalogAdminPage />);

    await user.click(await screen.findByRole("button", { name: /Linen dress/ }));
    await user.click(screen.getByRole("button", { name: /Cotton shawl/ }));
    resolveSecond({ ...secondProduct, variants: [], media: [] });
    expect(await screen.findByRole("heading", { name: "Cotton shawl" })).toBeInTheDocument();
    resolveFirst({ ...product, variants: [], media: [] });

    await waitFor(() => expect(screen.getByRole("heading", { name: "Cotton shawl" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Linen dress" })).not.toBeInTheDocument();
  });

  it("keeps the latest product status filter when list responses resolve out of order", async () => {
    const draftProduct = { ...product, title: "Draft product" };
    const archivedProduct = { ...product, id: "323e4567-e89b-12d3-a456-426614174000", title: "Archived product", status: "ARCHIVED" as const };
    let resolveDraft!: (value: { items: typeof product[]; next_cursor: string | null }) => void;
    const draftResults = new Promise<{ items: typeof product[]; next_cursor: string | null }>((resolve) => { resolveDraft = resolve; });
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff", email: "owner@example.test", name: "Owner", totp_enabled: true,
        permission_keys: ["catalog.read"],
      });
      if (path === "admin/catalog/products?limit=50") return Promise.resolve({ items: [product], next_cursor: null });
      if (path === "admin/catalog/products?limit=50&status=DRAFT") return draftResults;
      if (path === "admin/catalog/products?limit=50&status=ARCHIVED") return Promise.resolve({ items: [archivedProduct], next_cursor: null });
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CatalogAdminPage />);

    await screen.findByRole("button", { name: /Linen dress/ });
    const filter = screen.getByRole("combobox", { name: "Filter products by status" });
    await user.selectOptions(filter, "DRAFT");
    await user.selectOptions(filter, "ARCHIVED");
    expect(await screen.findByRole("button", { name: /Archived product/ })).toBeInTheDocument();
    resolveDraft({ items: [draftProduct], next_cursor: null });

    await waitFor(() => expect(screen.getByRole("button", { name: /Archived product/ })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /Draft product/ })).not.toBeInTheDocument();
  });
});
