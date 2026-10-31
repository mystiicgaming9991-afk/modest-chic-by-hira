import type { MetadataRoute } from "next";
import { publicSiteUrl } from "@/lib/server/public-catalog";
export const dynamic = "force-static";
export default function robots(): MetadataRoute.Robots {
  const url = publicSiteUrl();
  return { rules: { userAgent: "*", allow: "/", disallow: ["/cart/", "/wishlist/", "/checkout/"] }, ...(url ? { sitemap: new URL("/sitemap.xml", url).toString() } : {}) };
}
