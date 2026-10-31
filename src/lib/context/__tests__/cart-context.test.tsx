import { describe, it, expect, beforeEach, afterEach, vi, vitest } from "vitest";
import { CartProvider, useCart } from "@/lib/context/cart-context";
import { products } from "@/lib/data";
import type { ReactNode } from "react";

// We need to mock useCatalog to return stable preview data for CartProvider.
// CartProvider depends on useCatalog for mode, products, getLineDetails etc.
const { catalogMode } = vi.hoisted(() => ({ catalogMode: { value: "preview" as "preview" | "live" } }));

vitest.mock("@/lib/context/catalog-context", () => ({
  CatalogProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useCatalog: () => ({
    products: products,
    categories: [],
    collections: [],
    mode: catalogMode.value,
    error: null,
    retry: () => {},
  }),
}));

import { CatalogProvider } from "@/lib/context/catalog-context";
import { render, renderHook, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Component that renders cart state for testing
function CartConsumer() {
  const { items, itemCount, subtotal, addItem, removeItem } = useCart();

  return (
    <div>
      <span data-testid="item-count">{itemCount}</span>
      <span data-testid="subtotal">{subtotal}</span>
      <ul data-testid="items">
        {items.map((item) => (
          <li key={item.lineId} data-testid={`item-${item.lineId}`}>
            {item.productSlug}::{item.variantId} × {item.quantity}
          </li>
        ))}
      </ul>
      <button
        data-testid="add-test-item"
        onClick={async () => {
          await addItem("v1", "premium-chiffon-hijab", 1);
        }}
      >
        Add Item
      </button>
      <button
        data-testid="remove-item"
        onClick={async () => {
          const line = items.find((i) => i.productSlug === "premium-chiffon-hijab");
          if (line) await removeItem(line.lineId);
        }}
      >
        Remove
      </button>
    </div>
  );
}

function renderCart() {
  return render(
    <CatalogProvider>
      <CartProvider>
        <CartConsumer />
      </CartProvider>
    </CatalogProvider>
  );
}

describe("CartContext (preview mode)", () => {
  beforeEach(() => {
    catalogMode.value = "preview";
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("starts with empty cart after hydration", async () => {
    renderCart();
    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("0");
    });
    expect(screen.getByTestId("subtotal").textContent).toBe("0");
  });

  it("adds an item to the cart in preview mode", async () => {
    renderCart();
    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("0");
    });

    await act(async () => {
      await userEvent.click(screen.getByTestId("add-test-item"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("1");
    });
    expect(screen.getByTestId("subtotal").textContent).toBe("1850");
  });

  it("removes an item from the cart in preview mode", async () => {
    renderCart();
    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("0");
    });

    await act(async () => {
      await userEvent.click(screen.getByTestId("add-test-item"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("1");
    });

    await act(async () => {
      await userEvent.click(screen.getByTestId("remove-item"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("0");
    });
  });

  it("subtotal reflects item price", async () => {
    renderCart();
    await waitFor(() => {
      expect(screen.getByTestId("item-count").textContent).toBe("0");
    });

    await act(async () => {
      await userEvent.click(screen.getByTestId("add-test-item"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("subtotal").textContent).toBe("1850");
    });
  });
});

describe("CartContext (live mode)", () => {
  beforeEach(() => {
    catalogMode.value = "live";
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("keeps a successful add when the initial cart read returns an older snapshot", async () => {
    let resolveInitialRead!: (response: Response) => void;
    const initialRead = new Promise<Response>((resolve) => { resolveInitialRead = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/commerce/cart") return initialRead;
      if (String(input) === "/api/commerce/cart/items" && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ items: [
          { id: "line-1", variant_id: "v1", quantity: 1 },
        ] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      throw new Error(`Unexpected cart request: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <CatalogProvider><CartProvider>{children}</CartProvider></CatalogProvider>
    );
    const { result } = renderHook(() => useCart(), { wrapper });
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 0)); });
    expect(fetchMock).toHaveBeenCalledWith("/api/commerce/cart", { cache: "no-store" });

    await act(async () => {
      expect(await result.current.addItem("v1", "premium-chiffon-hijab", 1)).toBe(true);
    });
    expect(result.current.itemCount).toBe(1);

    await act(async () => {
      resolveInitialRead(new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
      await initialRead;
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    expect(result.current.itemCount).toBe(1);
  });
});
