import { connection } from "next/server";
import { Suspense } from "react";
import CollectionPageClient from "./collection-page-client";

export default function CollectionPage({ params }: { params: Promise<{ slug: string }> }) {
  return <>
    <Suspense fallback={null}><CollectionMetadataConnection /></Suspense>
    <Suspense fallback={<div className="container-page py-20" role="status">Loading collection…</div>}>
      <CollectionPageClient params={params} />
    </Suspense>
  </>;
}

async function CollectionMetadataConnection() {
  await connection();
  return null;
}
