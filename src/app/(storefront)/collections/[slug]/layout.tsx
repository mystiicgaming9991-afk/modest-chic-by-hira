import type { Metadata } from "next";
import { Suspense } from "react";
import { humanizeSlug, publicDescription, publicSiteUrl, readPublicCatalog, type PublicCollectionMetadata } from "@/lib/server/public-catalog";

export async function generateMetadata({ params }: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const data = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)
    ? await readPublicCatalog<{ items: PublicCollectionMetadata[] }>("collections")
    : null;
  const collection = data?.items.find((item) => item.slug === slug);
  if (!collection) {
    return {
      title: `${humanizeSlug(slug)} | Modest Chic`,
      robots: { index: false, follow: false },
    };
  }

  const title = `${collection.name} | Modest Chic`;
  const description = publicDescription(
    collection.description,
    `Explore the ${collection.name} collection from Modest Chic by Hira & Muqadas.`,
  );
  const siteUrl = publicSiteUrl();
  const canonicalPath = `/collections/${encodeURIComponent(slug)}`;
  return {
    title,
    description,
    alternates: siteUrl ? { canonical: new URL(canonicalPath, siteUrl).toString() } : undefined,
    openGraph: {
      title,
      description,
      type: "website",
      url: siteUrl ? new URL(canonicalPath, siteUrl).toString() : undefined,
    },
  };
}

export default function CollectionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Suspense fallback={<CollectionSkeleton />}>{children}</Suspense>;
}

function CollectionSkeleton() {
  return (
    <div className="bg-cream min-h-screen">
      <div className="bg-warm-cream py-12">
        <div className="container-page space-y-3">
          <div className="h-4 w-24 skeleton" />
          <div className="h-8 w-64 skeleton" />
          <div className="h-5 w-80 skeleton" />
        </div>
      </div>
      <div className="container-page py-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="aspect-[3/4] rounded-2xl skeleton" />
          ))}
        </div>
      </div>
    </div>
  );
}
