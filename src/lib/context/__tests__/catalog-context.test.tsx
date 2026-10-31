import { useState } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CatalogProvider, useCatalog } from "../catalog-context";

function product(id: string, slug: string, title: string) {
  return {
    id,
    slug,
    title,
    description: `${title} description`,
    fabric: "Cotton",
    care: "Hand wash",
    dimensions: "180 × 70 cm",
    category: "hijabs",
    categories: id === "p-1" ? ["hijabs", "occasion"] : ["hijabs"],
    collections: ["everyday-essentials"],
    is_new: true,
    is_featured: false,
    primary_image: { object_key: "/images/cotton-hijab.webp", alt_text: `${title} in sand` },
    variants: [{
      id: `${id}-variant`,
      sku: `${id}-sku`,
      color_name: "Warm Sand",
      color_hex: "#D4C5B9",
      price_minor: 155000,
      sale_price_minor: 145000,
      available_quantity: 3,
    }],
  };
}

function CatalogProbe() {
  const { mode, products, categories, collections, error, retry, loadPopularityOrder } = useCatalog();
  const [popularSlugs, setPopularSlugs] = useState<string[]>([]);
  return (
    <div>
      <p>Mode: {mode}</p>
      {error && <p role="alert">{error}</p>}
      {products.map((item) => <p key={item.id}>{item.title} · {item.variants[0]?.price} · {item.variants[0]?.salePrice} · {item.displayImage} · {item.categories?.join(",")}</p>)}
      {categories.map((item) => <p key={item.id}>Category: {item.title} ({item.productCount})</p>)}
      {collections.map((item) => <p key={item.id}>Collection: {item.title}</p>)}
      <p>Popular: {popularSlugs.join(", ")}</p>
      <button onClick={retry}>Retry catalog</button>
      <button onClick={() => void loadPopularityOrder().then(setPopularSlugs)}>Load popularity</button>
    </div>
  );
}

function renderCatalog() {
  return render(<CatalogProvider><CatalogProbe /></CatalogProvider>);
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("catalog API integration", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads every live product page and maps API values for storefront consumers", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("catalog/products?limit=100")) {
        return jsonResponse({ items: [product("p-1", "sand-hijab", "Sand Hijab")], next_cursor: "page-2" });
      }
      if (url.endsWith("catalog/products?limit=100&after=page-2")) {
        return jsonResponse({ items: [product("p-2", "rose-hijab", "Rose Hijab")], next_cursor: null });
      }
      if (url.endsWith("catalog/categories")) {
        return jsonResponse({ items: [
          { id: "category-1", slug: "hijabs", name: "Hijabs", description: "Everyday hijabs" },
          { id: "category-2", slug: "occasion", name: "Occasion", description: "Occasion pieces" },
        ] });
      }
      if (url.endsWith("catalog/collections")) {
        return jsonResponse({ items: [{ id: "collection-1", slug: "everyday-essentials", name: "Everyday Essentials", description: "Daily favorites" }] });
      }
      if (url.includes("sort=popular")) {
        return jsonResponse({ items: [product("p-2", "rose-hijab", "Rose Hijab"), product("p-1", "sand-hijab", "Sand Hijab")], next_cursor: null });
      }
      throw new Error(`Unexpected catalog request: ${url}`);
    });

    renderCatalog();
    expect(await screen.findByText("Mode: live")).toBeInTheDocument();
    expect(screen.getByText("Sand Hijab · 1550 · 1450 · /images/cotton-hijab.webp · hijabs,occasion")).toBeInTheDocument();
    expect(screen.getByText("Rose Hijab · 1550 · 1450 · /images/cotton-hijab.webp · hijabs")).toBeInTheDocument();
    expect(screen.getByText("Category: Hijabs (2)")).toBeInTheDocument();
    expect(screen.getByText("Category: Occasion (1)")).toBeInTheDocument();
    expect(screen.getByText("Collection: Everyday Essentials")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Load popularity" }));
    expect(await screen.findByText("Popular: rose-hijab, sand-hijab")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/commerce/catalog/products?sort=popular&limit=100", { cache: "no-store" });
  });

  it("shows catalog failures and recovers through the preview response on retry", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ message: "Catalog service is unavailable." }, 503))
      .mockResolvedValueOnce(jsonResponse({ preview: true, items: [] }));

    renderCatalog();
    expect(await screen.findByRole("alert")).toHaveTextContent("Catalog service is unavailable.");
    await userEvent.click(screen.getByRole("button", { name: "Retry catalog" }));

    expect(await screen.findByText("Mode: preview")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
