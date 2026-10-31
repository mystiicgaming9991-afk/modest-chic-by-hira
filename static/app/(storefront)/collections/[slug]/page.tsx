import CollectionPageClient from "./collection-page-client";
import { staticCatalog } from "@/lib/static-catalog";
export const dynamicParams = false;
export function generateStaticParams() { return staticCatalog.collections.map(({ slug }) => ({ slug })); }
export default function CollectionPage({ params }: { params: Promise<{ slug: string }> }) {
  return <CollectionPageClient params={params} />;
}
