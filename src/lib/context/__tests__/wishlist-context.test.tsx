import { describe, it, expect } from "vitest";
import { WishlistProvider, useWishlist } from "@/lib/context/wishlist-context";
import { products } from "@/lib/data";
import type { ReactNode } from "react";

// Mock catalog context
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

import { CatalogProvider } from "@/lib/context/catalog-context";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

function WishlistConsumer() {
  const { items, count, toggle, remove } = useWishlist();

  return (
    <div>
      <span data-testid="wishlist-count">{count}</span>
      <span data-testid="wishlist-items-raw">{items.join(",")}</span>
      <ul data-testid="wishlist-items">
        {items.map((slug) => (
          <li key={slug} data-testid={`wl-${slug}`}>
            {slug}
          </li>
        ))}
      </ul>
      <button
        data-testid="toggle-premium-chiffon"
        onClick={() => toggle("premium-chiffon-hijab")}
      >
        Toggle
      </button>
      <button
        data-testid="remove-premium-chiffon"
        onClick={() => remove("premium-chiffon-hijab")}
      >
        Remove
      </button>
    </div>
  );
}

function renderWishlist() {
  return render(
    <CatalogProvider>
      <WishlistProvider>
        <WishlistConsumer />
      </WishlistProvider>
    </CatalogProvider>
  );
}

describe("WishlistContext", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts empty after hydration", async () => {
    renderWishlist();
    await waitFor(() => {
      expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
    });
  });

  it("can toggle an item in", async () => {
    renderWishlist();
    // Wait for initial hydration
    await waitFor(() => {
      expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
    });

    await userEvent.click(screen.getByTestId("toggle-premium-chiffon"));

    // Toggle is synchronous in the context
    expect(screen.getByTestId("wishlist-count").textContent).toBe("1");
    expect(screen.getByTestId("wishlist-items-raw").textContent).toBe("premium-chiffon-hijab");
  });

  it("can toggle an item out", async () => {
    renderWishlist();
    await waitFor(() => {
      expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
    });

    await userEvent.click(screen.getByTestId("toggle-premium-chiffon"));
    expect(screen.getByTestId("wishlist-count").textContent).toBe("1");

    await userEvent.click(screen.getByTestId("toggle-premium-chiffon"));
    expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
  });

  it("remove works", async () => {
    renderWishlist();
    await waitFor(() => {
      expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
    });

    await userEvent.click(screen.getByTestId("toggle-premium-chiffon"));
    expect(screen.getByTestId("wishlist-count").textContent).toBe("1");

    await userEvent.click(screen.getByTestId("remove-premium-chiffon"));
    expect(screen.getByTestId("wishlist-count").textContent).toBe("0");
  });
});