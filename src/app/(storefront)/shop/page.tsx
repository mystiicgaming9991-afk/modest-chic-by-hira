import ShopClient from "./shop-client";
import { Suspense } from "react";

type ShopSearchParams = Promise<{ q?: string | string[]; category?: string | string[] }>;

async function ShopContent({ searchParams }: { searchParams: ShopSearchParams }) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.slice(0, 80) : "";
  const requestedCategory = typeof params.category === "string" ? params.category : "";
  const category = requestedCategory || null;

  return <ShopClient key={`${category ?? "all"}:${query}`} initialCategory={category} initialQuery={query} />;
}

export default function ShopPage({
  searchParams,
}: {
  searchParams: ShopSearchParams;
}) {
  return (
    <Suspense fallback={<div className="container-page min-h-[60vh] py-16"><p className="label-text text-terracotta">The Modest Chic edit</p><h1 className="heading-lg mt-3 text-charcoal">Explore the collection</h1><p className="mt-4 text-charcoal/75">Loading pieces...</p></div>}>
      <ShopContent searchParams={searchParams} />
    </Suspense>
  );
}
