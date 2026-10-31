import ProductPageClient from "./product-page-client";
import { staticCatalog } from "@/lib/static-catalog";
export const dynamicParams = false;
export function generateStaticParams() { return staticCatalog.products.map(({ slug }) => ({ slug })); }
export default function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  return <ProductPageClient params={params} />;
}
