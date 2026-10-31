import type { MetadataRoute } from "next";
import { staticCatalog } from "@/lib/static-catalog";
import { publicSiteUrl } from "@/lib/server/public-catalog";
export const dynamic = "force-static";
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = publicSiteUrl();
  if (!origin) return [];
  return ["/", "/shop/", "/about/", "/contact/", "/faq/", "/shipping/", "/returns/", "/privacy/", ...staticCatalog.collections.map(({ slug }) => `/collections/${slug}/`), ...staticCatalog.products.map(({ slug }) => `/shop/${slug}/`)].map((path) => ({ url: new URL(path, origin).toString() }));
}
