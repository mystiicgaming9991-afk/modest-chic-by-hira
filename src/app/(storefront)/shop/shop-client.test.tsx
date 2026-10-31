import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ShopClient from "./shop-client";

const { useCatalog } = vi.hoisted(() => ({ useCatalog: vi.fn() }));

vi.mock("next/image", () => ({
  default: ({ alt }: { alt?: string }) => <span role="img" aria-label={alt ?? ""} />,
}));
vi.mock("@/components/ui/product-card", () => ({
  ProductCard: ({ product }: { product: { title: string } }) => <div>{product.title}</div>,
}));
vi.mock("@/lib/context/catalog-context", () => ({ useCatalog }));

describe("mobile shop filters", () => {
  beforeEach(() => {
    useCatalog.mockReturnValue({
      products: [
        {
          id: "product-1",
          slug: "occasion-hijab",
          title: "Occasion Hijab",
          description: "",
          fabric: "Chiffon",
          dimensions: "",
          care: "",
          category: "hijabs",
          categories: ["hijabs", "occasion"],
          collections: [],
          tags: [],
          variants: [{ id: "variant-1", name: "Rose", color: "Rose", colorHex: "#000", sku: "sku-1", price: 1000, stock: 2 }],
          displayImage: "/placeholder.png",
          displayImageAlt: "Occasion Hijab",
          displayImageKind: "brand",
          displayImageNote: "",
          rating: 0,
          reviewCount: 0,
          isNew: false,
          isBestSeller: false,
          isFeatured: false,
        },
        {
          id: "product-2",
          slug: "daily-hijab",
          title: "Daily Hijab",
          description: "",
          fabric: "Cotton",
          dimensions: "",
          care: "",
          category: "hijabs",
          categories: ["hijabs"],
          collections: [],
          tags: [],
          variants: [{ id: "variant-2", name: "Sand", color: "Sand", colorHex: "#fff", sku: "sku-2", price: 900, stock: 1 }],
          displayImage: "/placeholder.png",
          displayImageAlt: "Daily Hijab",
          displayImageKind: "brand",
          displayImageNote: "",
          rating: 0,
          reviewCount: 0,
          isNew: false,
          isBestSeller: false,
          isFeatured: false,
        },
      ],
      categories: [
        { id: "category-1", slug: "hijabs", title: "Hijabs", description: "", image: "", productCount: 2 },
        { id: "category-2", slug: "occasion", title: "Occasion", description: "", image: "", productCount: 1 },
      ],
      mode: "preview",
      error: null,
      retry: vi.fn(),
      loadPopularityOrder: vi.fn().mockResolvedValue([]),
    });
    document.body.style.overflow = "";
  });

  it("isolates the filter dialog, traps focus, and restores page state on Escape", async () => {
    const user = userEvent.setup();
    render(
      <>
        <div id="site-announcement">Announcement</div>
        <header id="site-header"><button>Menu</button></header>
        <main id="site-main"><ShopClient initialCategory={null} initialQuery="" /></main>
        <footer id="site-footer">Footer</footer>
      </>,
    );
    const trigger = screen.getByRole("button", { name: "Open filters" });
    document.body.style.overflow = "clip";

    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "Filter products" });
    const closeButton = within(dialog).getByRole("button", { name: "Close filters" });
    expect(closeButton).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
    for (const id of ["site-announcement", "site-header", "site-main", "site-footer"]) {
      expect(document.getElementById(id)).toHaveAttribute("inert");
      expect(document.getElementById(id)).toHaveAttribute("aria-hidden", "true");
    }

    const lastButton = within(dialog).getByRole("button", { name: "Show 2 Results" });
    await user.tab({ shift: true });
    expect(lastButton).toHaveFocus();
    await user.tab();
    expect(closeButton).toHaveFocus();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Filter products" })).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe("clip");
    expect(document.getElementById("site-main")).not.toHaveAttribute("inert");
    expect(document.getElementById("site-main")).not.toHaveAttribute("aria-hidden");
    document.body.style.overflow = "";
  });

  it("includes products in every published category membership", async () => {
    const user = userEvent.setup();
    render(<ShopClient initialCategory="occasion" initialQuery="" />);

    expect(screen.getByText("1 product")).toBeInTheDocument();
    expect(screen.getByText("Occasion Hijab")).toBeInTheDocument();
    expect(screen.queryByText("Daily Hijab")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Occasion (1)" }));
    expect(screen.getByText("2 products")).toBeInTheDocument();
    expect(screen.getByText("Daily Hijab")).toBeInTheDocument();
  });
});
