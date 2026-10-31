import { isStaticStorefront } from "@/lib/storefront-mode";
import { staticCatalog } from "@/lib/static-catalog";

export interface PublicCollectionMetadata {
  slug: string;
  name: string;
  description: string | null;
}

export async function readPublicCatalog<T>(path: string): Promise<T | null> {
  if (isStaticStorefront()) {
    if (path === "collections") return { items: staticCatalog.collections.map((item) => ({ ...item, name: item.title })) } as T;
    if (path.startsWith("products/")) {
      const product = staticCatalog.products.find((item) => item.slug === decodeURIComponent(path.slice(9)));
      return product ? { ...product, primary_image: { object_key: product.displayImage, alt_text: product.displayImageAlt } } as T : null;
    }
    return null;
  }
  const apiBase = process.env.COMMERCE_API_URL;
  if (!apiBase || path.startsWith("/") || path.includes("..")) return null;
  try {
    const response = await fetch(new URL(`/api/v1/catalog/${path}`, apiBase), {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return null;
    return await response.json() as T;
  } catch {
    return null;
  }
}

export function publicSiteUrl(): URL | null {
  const configuredUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (!configuredUrl) return null;
  try {
    const url = new URL(configuredUrl);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

export function publicDescription(value: string | null, fallback: string): string {
  return value?.replace(/\s+/g, " ").trim().slice(0, 200) || fallback;
}

export function publicCatalogImage(objectKey: string | undefined): string | undefined {
  return objectKey?.startsWith("/images/") ? objectKey : undefined;
}

export function humanizeSlug(slug: string): string {
  return slug.split("-").filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ") || "Product";
}
