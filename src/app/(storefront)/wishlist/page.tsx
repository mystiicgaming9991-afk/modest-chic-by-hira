"use client";

import Link from "next/link";
import { ArrowRight, Heart, ShoppingBag } from "lucide-react";
import { ProductCard } from "@/components/ui/product-card";
import { useWishlist } from "@/lib/context/wishlist-context";
import { useCart } from "@/lib/context/cart-context";
import { useToast } from "@/lib/context/toast-context";

export default function WishlistPage() {
  const { getProducts } = useWishlist();
  const { addItem } = useCart();
  const { addToast } = useToast();
  const saved = getProducts();

  const addAll = async () => {
    let added = 0;
    for (const product of saved) {
      const variant = product.variants.find((item) => item.stock > 0);
      if (!variant) continue;
      if (await addItem(variant.id, product.slug, 1)) added++;
    }
    if (added) addToast({ type: "cart", message: `${added} item${added === 1 ? "" : "s"} added to cart`, actionLabel: "View Cart", actionHref: "/cart" });
  };

  return (
    <div className="min-h-[65vh] bg-cream">
      <div className="container-page py-10 md:py-14">
        <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="label-text mb-2 text-terracotta">Your edit</p>
            <h1 className="heading-lg text-charcoal">Saved pieces</h1>
            <p className="mt-2 text-sm text-charcoal/75">{saved.length} {saved.length === 1 ? "piece" : "pieces"} in your wishlist</p>
          </div>
          {saved.length > 0 && <button onClick={addAll} className="inline-flex w-fit items-center gap-2 rounded-full bg-charcoal px-5 py-3 text-sm font-medium text-cream hover:bg-deep-rust"><ShoppingBag className="h-4 w-4" /> Add available to cart</button>}
        </div>
        {saved.length ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 md:gap-6 lg:grid-cols-4">
            {saved.map((product, index) => <ProductCard key={product.id} product={product} preloadImage={index === 0} />)}
          </div>
        ) : (
          <div className="rounded-3xl border border-sand bg-white px-6 py-16 text-center">
            <span className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-warm-cream text-terracotta"><Heart className="h-7 w-7" /></span>
            <h2 className="heading-sm mb-3 text-charcoal">No saved pieces yet</h2>
            <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-charcoal/75">Tap the heart on a piece you love and it will appear here for later.</p>
            <Link href="/shop" className="inline-flex items-center gap-2 rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-cream hover:bg-deep-rust">Explore the collection <ArrowRight className="h-4 w-4" /></Link>
          </div>
        )}
      </div>
    </div>
  );
}
