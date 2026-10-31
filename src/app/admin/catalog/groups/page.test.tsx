import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CatalogGroupsPage from "./page";

const { staffJson, replace } = vi.hoisted(() => ({ staffJson: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson, jsonBody: vi.fn() }));

const firstProduct = "11111111-1111-4111-8111-111111111111";
const secondProduct = "22222222-2222-4222-8222-222222222222";
const firstCategory = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const secondCategory = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const collectionId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

describe("catalog group membership loading", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockReset();
  });

  it("ignores an older product membership response after staff switch products", async () => {
    const categoryResolvers = new Map<string, (ids: string[]) => void>();
    const tagResolvers = new Map<string, (ids: string[]) => void>();
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({
        id: "staff", email: "owner@example.test", name: "Owner", totp_enabled: true,
        permission_keys: ["catalog.read", "catalog.write"],
      });
      if (path === "admin/catalog/categories") return Promise.resolve({ items: [
        { id: firstCategory, slug: "first", name: "First category", description: null, parent_id: null, sort_order: 0, status: "DRAFT", created_at: "", updated_at: "", children: [] },
        { id: secondCategory, slug: "second", name: "Second category", description: null, parent_id: null, sort_order: 1, status: "DRAFT", created_at: "", updated_at: "", children: [] },
      ] });
      if (path === "admin/catalog/collections") return Promise.resolve({ items: [] });
      if (path === "admin/catalog/tags") return Promise.resolve({ items: [] });
      if (path.startsWith("admin/catalog/products?")) return Promise.resolve({ items: [
        { id: firstProduct, slug: "first-product", title: "First product", status: "DRAFT", updated_at: "2026-10-25T10:00:00Z" },
        { id: secondProduct, slug: "second-product", title: "Second product", status: "DRAFT", updated_at: "2026-10-25T10:00:00Z" },
      ], next_cursor: null });
      const categoryMatch = path.match(/^admin\/catalog\/products\/([^/]+)\/categories$/);
      if (categoryMatch) return new Promise<string[]>((resolve) => categoryResolvers.set(categoryMatch[1], resolve));
      const tagMatch = path.match(/^admin\/catalog\/products\/([^/]+)\/tags$/);
      if (tagMatch) return new Promise<string[]>((resolve) => tagResolvers.set(tagMatch[1], resolve));
      throw new Error(`Unexpected request: ${path}`);
    });

    const user = userEvent.setup();
    render(<CatalogGroupsPage />);
    const productSelect = await screen.findByRole("combobox", { name: "Product" });
    await screen.findByRole("option", { name: /First product/ });
    await user.selectOptions(productSelect, firstProduct);
    await waitFor(() => expect(categoryResolvers.has(firstProduct)).toBe(true));
    await user.selectOptions(productSelect, secondProduct);
    await waitFor(() => expect(categoryResolvers.has(secondProduct)).toBe(true));

    categoryResolvers.get(secondProduct)?.([secondCategory]);
    tagResolvers.get(secondProduct)?.([]);
    categoryResolvers.get(firstProduct)?.([firstCategory]);
    tagResolvers.get(firstProduct)?.([]);

    await waitFor(() => expect(screen.getByText("Second category", { selector: "span" })).toBeInTheDocument());
    expect(screen.queryByText("First category", { selector: "span" })).not.toBeInTheDocument();
  });

  it("uses PUT for collection and product membership updates", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return {
        id: "staff", email: "owner@example.test", name: "Owner", totp_enabled: true,
        permission_keys: ["catalog.read", "catalog.write"],
      };
      if (path === "admin/catalog/categories") return { items: [
        { id: firstCategory, slug: "first", name: "First category", description: null, parent_id: null, sort_order: 0, status: "DRAFT", created_at: "", updated_at: "", children: [] },
      ] };
      if (path === "admin/catalog/collections") return { items: [
        { id: collectionId, slug: "featured", name: "Featured", description: null, status: "DRAFT", starts_at: null, ends_at: null, created_at: "", updated_at: "2026-10-25T10:00:00Z" },
      ] };
      if (path === "admin/catalog/tags") return { items: [{ id: "tag-1", name: "New" }] };
      if (path.startsWith("admin/catalog/products?")) return { items: [
        { id: firstProduct, slug: "first-product", title: "First product", status: "DRAFT", updated_at: "2026-10-25T10:00:00Z" },
      ], next_cursor: null };
      if (path.endsWith("/products") || path.endsWith("/categories") || path.endsWith("/tags")) return [];
      return undefined;
    });

    const user = userEvent.setup();
    render(<CatalogGroupsPage />);

    await user.click(await screen.findByRole("button", { name: "Save collection order" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      `admin/catalog/collections/${collectionId}/products`,
      expect.objectContaining({ method: "PUT" }),
    ));

    await user.selectOptions(await screen.findByRole("combobox", { name: "Product" }), firstProduct);
    await user.click(await screen.findByRole("button", { name: "Save category order" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      `admin/catalog/products/${firstProduct}/categories`,
      expect.objectContaining({ method: "PUT" }),
    ));
    await user.click(await screen.findByRole("button", { name: "Save product tags" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      `admin/catalog/products/${firstProduct}/tags`,
      expect.objectContaining({ method: "PUT" }),
    ));
  });
});
