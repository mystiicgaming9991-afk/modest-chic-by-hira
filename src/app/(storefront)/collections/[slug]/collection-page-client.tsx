"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { ProductCard } from "@/components/ui/product-card";
import { useCatalog } from "@/lib/context/catalog-context";

export default function CollectionPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const { products, collections, mode, error, retry } = useCatalog();
  if (mode === "loading") return <div className="container-page py-20" role="status">Loading collection…</div>;
  if (mode === "error") return <div className="container-page py-20" role="alert"><p>{error}</p><button onClick={retry} className="mt-4 underline">Retry</button></div>;
  const collection = collections.find((c) => c.slug === slug);

  if (!collection) {
    notFound();
  }

  let collectionProducts = mode === "live" ? products.filter((product) => product.collections?.includes(slug)) : products;

  if (mode === "preview") switch (slug) {
    case "new-arrivals":
      collectionProducts = products.filter((p) => p.isNew);
      break;
    case "best-sellers":
      collectionProducts = products.filter((p) => p.isBestSeller);
      break;
    case "everyday-essentials":
      collectionProducts = products.filter((p) =>
        ["chiffon", "jersey", "cotton", "bamboo"].some((t) =>
          p.tags.includes(t)
        )
      );
      break;
    case "luxe-occasion":
      collectionProducts = products.filter((p) =>
        ["luxury", "satin", "silk", "formal", "bridal"].some((t) =>
          p.tags.includes(t)
        )
      );
      break;
    case "signature-neutrals":
      collectionProducts = products.filter((p) =>
        ["signature", "neutral", "iconic"].some((t) =>
          p.tags.includes(t)
        )
      );
      break;
  }

  return (
    <div className="bg-cream min-h-screen">
      {/* Hero Banner */}
      <div className="bg-warm-cream border-b border-sand/50">
        <div className="container-page py-12 md:py-16">
          <nav className="flex items-center gap-2 text-sm text-charcoal/75 mb-4">
            <Link href="/" className="hover:text-charcoal transition-colors">
              Home
            </Link>
            <ChevronRight className="w-3.5 h-3.5" />
            <span className="text-charcoal/70">Collections</span>
            <ChevronRight className="w-3.5 h-3.5" />
            <span className="text-charcoal/70">{collection.title}</span>
          </nav>
          <h1 className="heading-lg text-charcoal mb-3">{collection.title}</h1>
          <p className="body-base text-charcoal/75 max-w-lg">
            {collection.description}
          </p>
        </div>
      </div>

      {/* Products Grid */}
      <div className="container-page py-10">
        <section aria-labelledby="collection-products-heading">
          <h2 id="collection-products-heading" className="sr-only">Products in {collection.title}</h2>
          {collectionProducts.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
              {collectionProducts.map((product, index) => (
                <ProductCard key={product.id} product={product} preloadImage={index === 0} eagerImage={index < 4} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20">
              <h3 className="text-lg text-charcoal/75">No products in this collection yet.</h3>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
