import { describe, it, expect, vitest } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProductCard } from "@/components/ui/product-card";
import { products } from "@/lib/data";
import type { ReactNode } from "react";

// Mock the contexts that ProductCard depends on
vitest.mock("@/lib/context/catalog-context", () => ({
  CatalogProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useCatalog: () => ({
    products,
    categories: [],
    collections: [],
    mode: "preview" as const,
    error: null,
    retry: () => {},
  }),
}));

vitest.mock("@/lib/context/cart-context", () => {
  const fn = vitest.fn();
  return {
    CartProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    useCart: () => ({
      items: [],
      itemCount: 0,
      subtotal: 0,
      addItem: fn.mockResolvedValue(true),
      updateQuantity: vitest.fn(),
      removeItem: vitest.fn(),
      clearCart: vitest.fn(),
      loading: false,
      error: null,
      refreshCart: vitest.fn(),
      getLineDetails: vitest.fn(),
      getAllLines: vitest.fn().mockReturnValue([]),
      formatPrice: (amount: number) => `Rs. ${amount.toLocaleString("en-PK")}`,
    }),
  };
});

vitest.mock("@/lib/context/wishlist-context", () => ({
  WishlistProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useWishlist: () => ({
    items: [],
    count: 0,
    isWishlisted: () => false,
    toggle: vitest.fn(),
    add: vitest.fn(),
    remove: vitest.fn(),
    getProducts: () => [],
  }),
}));

vitest.mock("@/lib/context/toast-context", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useToast: () => ({
    toasts: [],
    addToast: vitest.fn(),
    removeToast: vitest.fn(),
  }),
}));

import { CatalogProvider } from "@/lib/context/catalog-context";
import { CartProvider } from "@/lib/context/cart-context";
import { WishlistProvider } from "@/lib/context/wishlist-context";
import { ToastProvider } from "@/lib/context/toast-context";

function renderProductCard(product: (typeof products)[number], imageOptions: { preloadImage?: boolean; eagerImage?: boolean } = {}) {
  return render(
    <ToastProvider>
      <CatalogProvider>
        <CartProvider>
          <WishlistProvider>
            <ProductCard product={product} {...imageOptions} />
          </WishlistProvider>
        </CartProvider>
      </CatalogProvider>
    </ToastProvider>
  );
}

describe("ProductCard", () => {
  const premiumChiffon = products[0]; // "Premium Chiffon Hijab" with 5 variants

  it("renders product title", () => {
    renderProductCard(premiumChiffon);
    expect(screen.getByText("Premium Chiffon Hijab")).toBeInTheDocument();
  });

  it("renders fabric label", () => {
    renderProductCard(premiumChiffon);
    expect(screen.getByText("Premium Korean Chiffon")).toBeInTheDocument();
  });

  it("renders price", () => {
    renderProductCard(premiumChiffon);
    // Min price across variants = 1550 (sale) or 1850
    expect(screen.getByText("From Rs. 1,550")).toBeInTheDocument();
  });

  it("links to product page", () => {
    renderProductCard(premiumChiffon);
    const links = screen.getAllByRole("link");
    const productLink = links.find((link) => link.getAttribute("href") === "/shop/premium-chiffon-hijab");
    expect(productLink).toBeTruthy();
  });

  it("shows new badge for new products", () => {
    const newProduct = products.find((p) => p.isNew)!;
    renderProductCard(newProduct);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("shows sold out badge for out of stock product", () => {
    const outOfStock = { ...premiumChiffon, variants: premiumChiffon.variants.map((v) => ({ ...v, stock: 0 })) };
    renderProductCard(outOfStock);
    expect(screen.getByText("Sold Out")).toBeInTheDocument();
  });

  it("renders wishlist button", () => {
    renderProductCard(premiumChiffon);
    const buttons = screen.getAllByRole("button");
    const wishlistButton = buttons.find((btn) =>
      btn.getAttribute("aria-label")?.includes("wishlist")
    );
    expect(wishlistButton).toBeTruthy();
  });

  it("does not show sold out badge when in stock", () => {
    renderProductCard(premiumChiffon);
    expect(screen.queryByText("Sold Out")).not.toBeInTheDocument();
  });

  it("eagerly loads above-the-fold product images without preloading every card", () => {
    renderProductCard(premiumChiffon, { eagerImage: true });
    expect(screen.getByRole("img", { name: premiumChiffon.displayImageAlt })).toHaveAttribute("loading", "eager");
  });
});
