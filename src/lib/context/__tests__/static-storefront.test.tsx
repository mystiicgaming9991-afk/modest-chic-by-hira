import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CartProvider, useCart } from "../cart-context";
import { CatalogProvider, useCatalog } from "../catalog-context";
import type { ReactNode } from "react";

vi.mock("@/lib/static-catalog", () => ({ staticCatalog: { products: [{ id: "scarf", slug: "scarf", title: "Real scarf", variants: [{ id: "rose", name: "Rose", sku: "SCARF-ROSE", price: 1000, stock: 4 }] }], categories: [], collections: [] } }));
const wrapper = ({ children }: { children: ReactNode }) => <CatalogProvider><CartProvider>{children}</CartProvider></CatalogProvider>;
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); localStorage.clear(); });

describe("published static catalogue and cart", () => {
  it("browses, saves, restores and removes cart items without any API requests", async () => {
    vi.stubEnv("NEXT_PUBLIC_STOREFRONT_MODE", "static");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const first = renderHook(() => ({ cart: useCart(), catalog: useCatalog() }), { wrapper });
    await waitFor(() => expect(first.result.current.cart.loading).toBe(false));
    expect(first.result.current.catalog.mode).toBe("live");
    await act(async () => { await first.result.current.cart.addItem("rose", "scarf", 2); });
    expect(first.result.current.cart.subtotal).toBe(2000);
    first.unmount();
    const second = renderHook(() => useCart(), { wrapper });
    await waitFor(() => expect(second.result.current.itemCount).toBe(2));
    await act(async () => { await second.result.current.updateQuantity(second.result.current.items[0].lineId, 3); });
    expect(second.result.current.subtotal).toBe(3000);
    await act(async () => { await second.result.current.removeItem(second.result.current.items[0].lineId); });
    expect(second.result.current.itemCount).toBe(0);
    expect(fetch).not.toHaveBeenCalled();
  });
});
