import type { Metadata } from "next";
import { Suspense } from "react";
import {
  humanizeSlug,
  publicCatalogImage,
  publicDescription,
  publicSiteUrl,
  readPublicCatalog,
} from "@/lib/server/public-catalog";

interface PublicProductMetadata {
  title: string;
  description: string | null;
  primary_image: { object_key: string; alt_text: string | null } | null;
}

export async function generateMetadata({ params }: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)
    ? await readPublicCatalog<PublicProductMetadata>(`products/${encodeURIComponent(slug)}`)
    : null;
  if (!product) {
    return {
      title: `${humanizeSlug(slug)} | Modest Chic`,
      robots: { index: false, follow: false },
    };
  }

  const title = `${product.title} | Modest Chic`;
  const description = publicDescription(
    product.description,
    `Shop ${product.title} from Modest Chic by Hira & Muqadas.`,
  );
  const siteUrl = publicSiteUrl();
  const canonicalPath = `/shop/${encodeURIComponent(slug)}`;
  const image = publicCatalogImage(product.primary_image?.object_key);

  return {
    title,
    description,
    alternates: siteUrl ? { canonical: new URL(canonicalPath, siteUrl).toString() } : undefined,
    openGraph: {
      title,
      description,
      type: "website",
      url: siteUrl ? new URL(canonicalPath, siteUrl).toString() : undefined,
      images: image && siteUrl ? [{ url: new URL(image, siteUrl).toString(), alt: product.primary_image?.alt_text || product.title }] : undefined,
    },
  };
}


export default function ProductLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Suspense fallback={<ProductSkeleton />}>{children}</Suspense>;
}

function ProductSkeleton() {
  return (
    <div className="bg-cream min-h-screen">
      <div className="container-page py-8">
        <div className="grid md:grid-cols-2 gap-8">
          <div className="aspect-[3/4] rounded-2xl skeleton" />
          <div className="space-y-6">
            <div className="h-4 w-24 skeleton" />
            <div className="h-8 w-72 skeleton" />
            <div className="h-6 w-32 skeleton" />
            <div className="h-12 w-full skeleton" />
          </div>
        </div>
      </div>
    </div>
  );
}
