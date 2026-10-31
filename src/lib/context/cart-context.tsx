"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import { formatPrice, type Product, type ProductVariant } from "@/lib/data";
import { trackProductEvent } from "@/lib/analytics";
import { isStaticStorefront } from "@/lib/storefront-mode";
import { useCatalog } from "@/lib/context/catalog-context";

// ============================================================
// Types
// ============================================================

export interface CartItem {
  /** Unique line id — stable across re-renders (variantId + productSlug) */
  lineId: string;
  variantId: string;
  productSlug: string;
  quantity: number;
  backendId?: string;
}

interface CartContextValue {
  items: CartItem[];
  itemCount: number;
  subtotal: number;
  addItem: (variantId: string, productSlug: string, quantity?: number) => Promise<boolean>;
  updateQuantity: (lineId: string, quantity: number) => Promise<boolean>;
  removeItem: (lineId: string) => Promise<boolean>;
  clearCart: () => void;
  loading: boolean;
  error: string | null;
  refreshCart: () => Promise<void>;
  /** Get full product + variant for a cart line */
  getLineDetails: (lineId: string) => {
    product: Product | undefined;
    variant: ProductVariant | undefined;
    lineTotal: number;
  } | null;
  getAllLines: () => Array<{
    lineId: string;
    product: Product | undefined;
    variant: ProductVariant | undefined;
    quantity: number;
    lineTotal: number;
  }>;
  formatPrice: (amount: number) => string;
}

// ============================================================
// Context
// ============================================================

const CartContext = createContext<CartContextValue | null>(null);

const cartStorageKey = () => isStaticStorefront() ? "modest-chic-static-cart-v1" : "modest-chic-cart";
const CART_EXPIRY_DAYS = 7;

function makeLineId(variantId: string, productSlug: string): string {
  return `${productSlug}::${variantId}`;
}

function loadCart(): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(cartStorageKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!parsed.items || !Array.isArray(parsed.items)) return [];

    // Check expiry
    if (parsed.timestamp) {
      const age = Date.now() - parsed.timestamp;
      const maxAge = CART_EXPIRY_DAYS * 24 * 60 * 60 * 1000;
      if (age > maxAge) {
        localStorage.removeItem(cartStorageKey());
        return [];
      }
    }

    // Validate items
    return parsed.items.filter(
      (item: unknown) =>
        item &&
        typeof item === "object" &&
        (item as CartItem).lineId &&
        (item as CartItem).variantId &&
        (item as CartItem).productSlug &&
        Number.isSafeInteger((item as CartItem).quantity) &&
        (item as CartItem).quantity > 0
    );
  } catch {
    return [];
  }
}

function saveCart(items: CartItem[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      cartStorageKey(),
      JSON.stringify({ items, timestamp: Date.now() })
    );
  } catch {
    // Storage full or unavailable — silently fail; items remain in memory
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const { products, mode } = useCatalog();
  const [items, setItems] = useState<CartItem[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isFirstRender = useRef(true);
  const pending = useRef(false);
  const cartRevision = useRef(0);
  const latestCartRead = useRef(0);

  const applyRemoteCart = useCallback((cart: { items: Array<{ id: string; variant_id: string; quantity: number }> }) => {
    setItems(cart.items.map((item) => {
      const product = products.find((entry) => entry.variants.some((variant) => variant.id === item.variant_id));
      const slug = product?.slug ?? "";
      return { lineId: makeLineId(item.variant_id, slug), backendId: item.id, variantId: item.variant_id, productSlug: slug, quantity: item.quantity };
    }));
  }, [products]);

  const refreshCart = useCallback(async () => {
    if (mode !== "live" || isStaticStorefront()) return;
    const requestId = ++latestCartRead.current;
    const revision = cartRevision.current;
    setLoading(true);
    try {
      const response = await fetch("/api/commerce/cart", { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message ?? "Cart could not be loaded.");
      if (requestId === latestCartRead.current && revision === cartRevision.current && !pending.current) {
        applyRemoteCart(body);
        setError(null);
      }
    } catch (cause) {
      if (requestId === latestCartRead.current && revision === cartRevision.current) {
        setError(cause instanceof Error ? cause.message : "Cart could not be loaded.");
      }
    } finally {
      if (requestId === latestCartRead.current) setLoading(false);
    }
  }, [applyRemoteCart, mode]);

  // Hydrate from localStorage on mount
  useEffect(() => {
    if (mode === "loading") return;
    const timer = window.setTimeout(() => {
      if (mode === "preview" || isStaticStorefront()) setItems(loadCart());
      else if (mode === "live" && !isStaticStorefront()) {
        // Clear stale preview cart from localStorage when switching to live mode
        // since variant IDs differ between preview (v1, v2) and live (UUIDs).
        try { localStorage.removeItem(cartStorageKey()); } catch { /* ignore */ }
        void refreshCart();
      }
      setHydrated(true);
      if (mode === "live" && !isStaticStorefront()) { /* loading is set by refreshCart */ }
      else setLoading(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [mode, refreshCart]);

  // Persist to localStorage on change (skip first render)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (hydrated && (mode === "preview" || isStaticStorefront())) {
      saveCart(items);
    }
  }, [items, hydrated, mode]);

  const mutate = useCallback(async (path: string, method: "POST" | "PATCH" | "DELETE", body?: object) => {
    if (pending.current) return false;
    pending.current = true;
    cartRevision.current += 1;
    try {
      const response = await fetch(`/api/commerce/${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Cart could not be updated.");
      applyRemoteCart(result);
      setError(null);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cart could not be updated.");
      return false;
    } finally {
      cartRevision.current += 1;
      pending.current = false;
    }
  }, [applyRemoteCart]);

  const itemCount = items.reduce((sum, item) => sum + item.quantity, 0);

  const subtotal = items.reduce((sum, item) => {
    const product = products.find((p) => p.slug === item.productSlug);
    const variant = product?.variants.find((v) => v.id === item.variantId);
    const price = variant?.salePrice ?? variant?.price ?? 0;
    return sum + price * item.quantity;
  }, 0);

  const addItem = useCallback(
    async (variantId: string, productSlug: string, quantity = 1) => {
      const eventProduct = products.find((product) => product.slug === productSlug);
      const eventVariant = eventProduct?.variants.find((variant) => variant.id === variantId);
      const previousQuantity = items.find((item) => item.variantId === variantId)?.quantity ?? 0;
      const addedQuantity = Math.max(0, Math.min(quantity, (eventVariant?.stock ?? 0) - previousQuantity));
      const reportAdd = () => { if (eventProduct && eventVariant) trackProductEvent("add_to_cart", eventProduct, eventVariant, addedQuantity); };
      if (mode === "live" && !isStaticStorefront()) {
        const existing = items.find((item) => item.variantId === variantId);
        const variant = products.find((product) => product.slug === productSlug)?.variants.find((entry) => entry.id === variantId);
        if (!variant || variant.stock < 1) return false;
        const success = await mutate("cart/items", "POST", { variant_id: variantId, quantity: Math.min((existing?.quantity ?? 0) + quantity, variant.stock) });
        if (success) reportAdd();
        return success;
      }
      const validVariant = products.find((product) => product.slug === productSlug)?.variants.find((variant) => variant.id === variantId);
      if (!validVariant || validVariant.stock < 1 || !Number.isSafeInteger(quantity) || quantity < 1) return false;
      setItems((prev) => {
        const lineId = makeLineId(variantId, productSlug);
        const existing = prev.find((i) => i.lineId === lineId);

        if (existing) {
          // Increment quantity, respecting available stock
          const product = products.find((p) => p.slug === productSlug);
          const variant = product?.variants.find((v) => v.id === variantId);
          const maxQty = variant?.stock ?? 99;
          const newQty = Math.min(existing.quantity + quantity, maxQty);
          return prev.map((i) =>
            i.lineId === lineId ? { ...i, quantity: newQty } : i
          );
        }

        const product = products.find((p) => p.slug === productSlug);
        const variant = product?.variants.find((v) => v.id === variantId);
        if (!variant || variant.stock < 1) return prev;
        return [...prev, { lineId, variantId, productSlug, quantity: Math.min(quantity, variant.stock) }];
      });
      reportAdd();
      return true;
    },
    [items, mode, mutate, products]
  );

  const updateQuantity = useCallback(async (lineId: string, quantity: number) => {
    if (!Number.isSafeInteger(quantity) || quantity < 1) return false;
    const item = items.find((entry) => entry.lineId === lineId);
    const product = products.find((entry) => entry.slug === item?.productSlug);
    const variant = product?.variants.find((entry) => entry.id === item?.variantId);
    const reportChange = () => {
      if (!item || !product || !variant) return;
      const delta = Math.min(quantity, variant.stock) - item.quantity;
      if (delta) trackProductEvent(delta > 0 ? "add_to_cart" : "remove_from_cart", product, variant, Math.abs(delta));
    };
    if (mode === "live" && !isStaticStorefront()) {
      if (!item?.backendId) return false;
      const success = await mutate(`cart/items/${encodeURIComponent(item.backendId)}`, "PATCH", { variant_id: item.variantId, quantity });
      if (success) reportChange();
      return success;
    }
    setItems((prev) =>
      prev.map((item) =>
        item.lineId === lineId
          ? { ...item, quantity: Math.min(quantity, products.find((product) => product.slug === item.productSlug)?.variants.find((variant) => variant.id === item.variantId)?.stock ?? 99) }
          : item
      )
    );
    reportChange();
    return true;
  }, [items, mode, mutate, products]);

  const removeItem = useCallback(async (lineId: string) => {
    const item = items.find((entry) => entry.lineId === lineId);
    const product = products.find((entry) => entry.slug === item?.productSlug);
    const variant = product?.variants.find((entry) => entry.id === item?.variantId);
    const reportRemove = () => { if (product && variant && item) trackProductEvent("remove_from_cart", product, variant, item.quantity); };
    if (mode === "live" && !isStaticStorefront()) {
      if (!item?.backendId) return false;
      const success = await mutate(`cart/items/${encodeURIComponent(item.backendId)}`, "DELETE");
      if (success) reportRemove();
      return success;
    }
    setItems((prev) => prev.filter((item) => item.lineId !== lineId));
    reportRemove();
    return true;
  }, [items, mode, mutate, products]);

  const clearCart = useCallback(() => {
    setItems([]);
  }, []);

  const getLineDetails = useCallback(
    (lineId: string) => {
      const item = items.find((i) => i.lineId === lineId);
      if (!item) return null;
      const product = products.find((p) => p.slug === item.productSlug);
      const variant = product?.variants.find((v) => v.id === item.variantId);
      const price = variant?.salePrice ?? variant?.price ?? 0;
      return {
        product,
        variant,
        lineTotal: price * item.quantity,
      };
    },
    [items, products]
  );

  const getAllLines = useCallback(() => {
    return items.map((item) => {
      const product = products.find((p) => p.slug === item.productSlug);
      const variant = product?.variants.find((v) => v.id === item.variantId);
      const price = variant?.salePrice ?? variant?.price ?? 0;
      return {
        lineId: item.lineId,
        product,
        variant,
        quantity: item.quantity,
        lineTotal: price * item.quantity,
      };
    });
  }, [items, products]);

  const value: CartContextValue = {
    items,
    itemCount,
    subtotal,
    addItem,
    updateQuantity,
    removeItem,
    clearCart,
    loading,
    error,
    refreshCart,
    getLineDetails,
    getAllLines,
    formatPrice,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error("useCart must be used within a <CartProvider>");
  }
  return ctx;
}
