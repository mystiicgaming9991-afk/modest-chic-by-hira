"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ShopClient from "./shop-client";
function ShopContent() {
  const params = useSearchParams();
  const query = (params.get("q") ?? "").slice(0, 80);
  const category = params.get("category");
  return <ShopClient key={`${category}:${query}`} initialCategory={category} initialQuery={query} />;
}
export default function ShopPage() { return <Suspense fallback={<p className="container-page py-20">Loading collection…</p>}><ShopContent /></Suspense>; }
