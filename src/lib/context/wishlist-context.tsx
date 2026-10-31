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
import { type Product } from "@/lib/data";
import { useCatalog } from "@/lib/context/catalog-context";

// ============================================================
// Types
// ============================================================

interface WishlistContextValue {
  items: string[]; // product slugs
  count: number;
  isWishlisted: (productSlug: string) => boolean;
  toggle: (productSlug: string) => void;
  add: (productSlug: string) => void;
  remove: (productSlug: string) => void;
  getProducts: () => Product[];
}

// ============================================================
// Context
// ============================================================

const WishlistContext = createContext<WishlistContextValue | null>(null);

const STORAGE_KEY = "modest-chic-wishlist";

function loadWishlist(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter(
        (item: unknown) => typeof item === "string" && item.length > 0
      );
    }
    return [];
  } catch {
    return [];
  }
}

function saveWishlist(items: string[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Silently fail — storage full
  }
}

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { products } = useCatalog();
  const [items, setItems] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const isFirstRender = useRef(true);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setItems(loadWishlist());
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (hydrated) {
      saveWishlist(items);
    }
  }, [items, hydrated]);

  const isWishlisted = useCallback(
    (productSlug: string) => items.includes(productSlug),
    [items]
  );

  const toggle = useCallback((productSlug: string) => {
    setItems((prev) =>
      prev.includes(productSlug)
        ? prev.filter((s) => s !== productSlug)
        : [...prev, productSlug]
    );
  }, []);

  const add = useCallback((productSlug: string) => {
    setItems((prev) => (prev.includes(productSlug) ? prev : [...prev, productSlug]));
  }, []);

  const remove = useCallback((productSlug: string) => {
    setItems((prev) => prev.filter((s) => s !== productSlug));
  }, []);

  const getProducts = useCallback(() => {
    return items
      .map((slug) => products.find((p) => p.slug === slug))
      .filter((p): p is Product => p !== undefined);
  }, [items, products]);

  const value: WishlistContextValue = {
    items,
    count: items.length,
    isWishlisted,
    toggle,
    add,
    remove,
    getProducts,
  };

  return (
    <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>
  );
}

export function useWishlist() {
  const ctx = useContext(WishlistContext);
  if (!ctx) {
    throw new Error("useWishlist must be used within a <WishlistProvider>");
  }
  return ctx;
}
