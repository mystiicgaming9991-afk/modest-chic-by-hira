import { connection } from "next/server";
import { Suspense } from "react";
import ProductPageClient from "./product-page-client";

export default function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  return <>
    <Suspense fallback={null}><ProductMetadataConnection /></Suspense>
    <Suspense fallback={<div className="container-page py-20" role="status">Loading product…</div>}>
      <ProductPageClient params={params} />
    </Suspense>
  </>;
}

async function ProductMetadataConnection() {
  await connection();
  return null;
}
