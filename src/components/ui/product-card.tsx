"use client";

import Link from "next/link";
import Image from "next/image";
import { Heart, ShoppingBag } from "lucide-react";
import { Badge } from "./badge";
import { useCart } from "@/lib/context/cart-context";
import { useWishlist } from "@/lib/context/wishlist-context";
import { useToast } from "@/lib/context/toast-context";
import type { Product } from "@/lib/data";
import { formatPrice } from "@/lib/data";

export function ProductCard({ product, preloadImage = false, eagerImage = false }: { product: Product; preloadImage?: boolean; eagerImage?: boolean }) {
  const { addItem } = useCart();
  const { isWishlisted, toggle: toggleWishlist } = useWishlist();
  const { addToast } = useToast();
  const availableVariant = product.variants.find((variant) => variant.stock > 0);
  const prices = product.variants.map((variant) => variant.salePrice ?? variant.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const isOutOfStock = !availableVariant;
  const wishlisted = isWishlisted(product.slug);

  const quickAdd = async () => {
    if (!availableVariant) return;
    if (!await addItem(availableVariant.id, product.slug, 1)) return;
    addToast({
      type: "cart",
      message: `${product.title} — ${availableVariant.name} added`,
      actionLabel: "View Cart",
      actionHref: "/cart",
    });
  };

  const toggleSaved = () => {
    toggleWishlist(product.slug);
    if (!wishlisted) {
      addToast({ type: "wishlist", message: `${product.title} saved to wishlist`, actionLabel: "View", actionHref: "/wishlist" });
    }
  };

  return (
    <article className="group relative animate-fade-in-up">
      <div className="relative mb-3 overflow-hidden rounded-2xl border border-[#d9cbc2] bg-[#e8dcd4] shadow-sm transition-all duration-300 group-hover:-translate-y-1 group-hover:shadow-lg group-hover:shadow-charcoal/10">
        <Link href={`/shop/${product.slug}`} className="block" aria-label={`View ${product.title}`}>
          <div className="relative aspect-[3/4] overflow-hidden bg-warm-cream">
            <Image src={product.displayImage} alt={product.displayImageAlt} fill {...(preloadImage ? { preload: true } : { loading: eagerImage ? "eager" : "lazy" })} sizes="(max-width: 640px) 45vw, (max-width: 1280px) 30vw, 21vw" className="object-cover object-center transition-transform duration-500 group-hover:scale-[1.04]" />
            <span className="absolute bottom-3 right-3 hidden rounded-full bg-cream/95 px-2.5 py-1 text-[10px] font-medium tracking-wide text-charcoal shadow-sm sm:block">{product.displayImageKind === "brand" ? "Collection photo" : product.displayImageKind === "illustration" ? "Illustrative image" : "Style reference"}</span>
          </div>
        </Link>
        <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1.5">
          {product.isNew && <Badge variant="new">New</Badge>}
          {product.isBestSeller && <Badge variant="bestseller">Featured</Badge>}
          {isOutOfStock && <Badge variant="outOfStock">Sold Out</Badge>}
          {product.variants.some((variant) => variant.salePrice) && !isOutOfStock && <Badge variant="sale">Sale</Badge>}
        </div>
        <div className="absolute right-3 top-3 flex flex-col gap-2">
          <button type="button" onClick={toggleSaved} className={`rounded-xl p-2.5 shadow-sm transition-colors ${wishlisted ? "bg-dusty-rose text-cream" : "bg-cream/95 text-charcoal hover:text-dusty-rose"}`} aria-label={`${wishlisted ? "Remove" : "Add"} ${product.title} ${wishlisted ? "from" : "to"} wishlist`}>
            <Heart className="h-4 w-4" fill={wishlisted ? "currentColor" : "none"} />
          </button>
          {!isOutOfStock && (
            <button type="button" onClick={quickAdd} className="rounded-xl bg-cream/95 p-2.5 text-charcoal shadow-sm transition-colors hover:bg-charcoal hover:text-cream" aria-label={`Add ${product.title} in ${availableVariant?.name} to cart`}>
              <ShoppingBag className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="pointer-events-none absolute bottom-3 left-3 flex gap-1.5 rounded-full bg-cream/90 px-2 py-1.5 shadow-sm" aria-label={`${product.variants.length} available shades`}>
          {product.variants.slice(0, 5).map((variant) => (
            <span key={variant.id} className={`h-3.5 w-3.5 rounded-full border border-charcoal/15 ${variant.stock === 0 ? "opacity-30" : ""}`} style={{ backgroundColor: variant.colorHex }} title={variant.name} />
          ))}
          {product.variants.length > 5 && <span className="self-center text-[10px] text-charcoal/70">+{product.variants.length - 5}</span>}
        </div>
      </div>
      <Link href={`/shop/${product.slug}`} className="block space-y-1.5">
        <p className="label-text text-charcoal/75">{product.fabric}</p>
        <h3 className="line-clamp-2 text-sm font-medium leading-snug text-charcoal transition-colors group-hover:text-terracotta sm:text-base">{product.title}</h3>
        <p className="text-sm font-semibold text-charcoal">{minPrice === maxPrice ? formatPrice(minPrice) : `From ${formatPrice(minPrice)}`}</p>
        <p className="text-[11px] leading-snug text-charcoal/75">{product.displayImageNote}</p>
      </Link>
    </article>
  );
}
