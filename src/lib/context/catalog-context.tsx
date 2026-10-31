"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { products as previewProducts, categories as previewCategories, collections as previewCollections, type Product, type Category, type Collection } from "@/lib/data";

import { isStaticStorefront } from "@/lib/storefront-mode";
import { staticCatalog } from "@/lib/static-catalog";

interface ApiProduct {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  fabric: string | null;
  care: string | null;
  dimensions: string | null;
  category: string;
  categories?: string[];
  collections: string[];
  is_new?: boolean;
  is_featured?: boolean;
  primary_image: { object_key: string; alt_text: string | null } | null;
  variants: Array<{ id: string; sku: string; color_name: string; color_hex: string | null; price_minor: number; sale_price_minor: number | null; available_quantity: number }>;
}

interface CatalogValue {
  products: Product[];
  categories: Category[];
  collections: Collection[];
  mode: "loading" | "preview" | "live" | "error";
  error: string | null;
  retry: () => void;
  loadPopularityOrder: () => Promise<string[]>;
}

const CatalogContext = createContext<CatalogValue | null>(null);

function mapProduct(item: ApiProduct): Product {
  const image = item.primary_image?.object_key;
  const localImage = image?.startsWith("/images/") ? image : "/images/product-placeholder.svg";
  return {
    id: item.id,
    slug: item.slug,
    title: item.title,
    description: item.description ?? "",
    fabric: item.fabric ?? "",
    care: item.care ?? "",
    dimensions: item.dimensions ?? "",
    category: item.category,
    categories: item.categories ?? (item.category ? [item.category] : []),
    collections: item.collections,
    tags: [],
    variants: item.variants.map((variant) => ({
      id: variant.id,
      name: variant.color_name,
      color: variant.color_name,
      colorHex: variant.color_hex ?? "#D4C5B9",
      sku: variant.sku,
      price: variant.price_minor / 100,
      salePrice: variant.sale_price_minor == null ? undefined : variant.sale_price_minor / 100,
      stock: variant.available_quantity,
    })),
    displayImage: localImage,
    displayImageAlt: item.primary_image?.alt_text ?? item.title,
    displayImageKind: "brand",
    displayImageNote: localImage.endsWith("product-placeholder.svg") ? "Product photo pending" : "Product photo",
    rating: 0,
    reviewCount: 0,
    isNew: item.is_new ?? false,
    isBestSeller: item.is_featured ?? false,
    isFeatured: item.is_featured ?? false,
  };
}

async function readJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message ?? "The catalog could not be loaded.");
  return body as T;
}

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<CatalogValue["mode"]>(isStaticStorefront() ? "live" : "loading");
  const [products, setProducts] = useState<Product[]>(isStaticStorefront() ? staticCatalog.products : []);
  const [categories, setCategories] = useState<Category[]>(isStaticStorefront() ? staticCatalog.categories : []);
  const [collections, setCollections] = useState<Collection[]>(isStaticStorefront() ? staticCatalog.collections : []);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [popularityOrder, setPopularityOrder] = useState<string[]>([]);
  const popularityRequest = useRef<Promise<string[]> | null>(null);
  const retry = useCallback(() => setRevision((value) => value + 1), []);
  const loadPopularityOrder = useCallback(async () => {
    if (isStaticStorefront()) return staticCatalog.products.map((product) => product.slug);
    if (mode === "preview") {
      return [...previewProducts]
        .sort((a, b) => Number(b.isBestSeller) - Number(a.isBestSeller))
        .map((product) => product.slug);
    }
    if (popularityOrder.length > 0) return popularityOrder;
    if (mode !== "live") return [];
    if (!popularityRequest.current) {
      popularityRequest.current = (async () => {
        const rows: ApiProduct[] = [];
        let cursor: string | null | undefined;
        do {
          const params = new URLSearchParams({ sort: "popular", limit: "100" });
          if (cursor) params.set("after", cursor);
          const page = await readJson<{ items: ApiProduct[]; next_cursor?: string | null }>(
            `/api/commerce/catalog/products?${params}`
          );
          rows.push(...page.items);
          cursor = page.next_cursor;
        } while (cursor);
        const slugs = rows.map((product) => product.slug);
        setPopularityOrder(slugs);
        return slugs;
      })().catch(() => {
        popularityRequest.current = null;
        return [];
      });
    }
    return popularityRequest.current;
  }, [mode, popularityOrder]);

  useEffect(() => {
    if (isStaticStorefront()) return;
    let active = true;
    async function load() {
      try {
        const first = await readJson<{ preview?: boolean; items: ApiProduct[]; next_cursor?: string | null }>("/api/commerce/catalog/products?limit=100");
        if (!active) return;
        if (first.preview) {
          popularityRequest.current = null;
          setPopularityOrder([]);
          setProducts(previewProducts);
          setCategories(previewCategories);
          setCollections(previewCollections);
          setMode("preview");
          return;
        }
        const rows = [...first.items];
        let cursor = first.next_cursor;
        while (cursor) {
          const page = await readJson<{ items: ApiProduct[]; next_cursor?: string | null }>(`/api/commerce/catalog/products?limit=100&after=${encodeURIComponent(cursor)}`);
          rows.push(...page.items);
          cursor = page.next_cursor;
        }
        const [categoryData, collectionData] = await Promise.all([
          readJson<{ items: Array<{ id: string; slug: string; name: string; description: string | null }> }>("/api/commerce/catalog/categories"),
          readJson<{ items: Array<{ id: string; slug: string; name: string; description: string | null }> }>("/api/commerce/catalog/collections"),
        ]);
        if (!active) return;
        popularityRequest.current = null;
        setPopularityOrder([]);
        setProducts(rows.map(mapProduct));
        setCategories(categoryData.items.map((item) => ({ id: item.id, slug: item.slug, title: item.name, description: item.description ?? "", image: "/images/product-placeholder.svg", productCount: rows.filter((product) => (product.categories ?? [product.category]).includes(item.slug)).length })));
        setCollections(collectionData.items.map((item) => ({ id: item.id, slug: item.slug, title: item.name, description: item.description ?? "", image: "/images/product-placeholder.svg", productCount: 0 })));
        setMode("live");
        setError(null);
      } catch (cause) {
        if (!active) return;
        setProducts([]);
        popularityRequest.current = null;
        setPopularityOrder([]);
        setCategories([]);
        setCollections([]);
        setMode("error");
        setError(cause instanceof Error ? cause.message : "The catalog could not be loaded.");
      }
    }
    void load();
    return () => { active = false; };
  }, [revision]);

  return <CatalogContext.Provider value={{ products, categories, collections, mode, error, retry, loadPopularityOrder }}>{children}</CatalogContext.Provider>;
}

export function useCatalog() {
  const value = useContext(CatalogContext);
  if (!value) throw new Error("useCatalog requires CatalogProvider");
  return value;
}
