"use client";

import { useState, use, useEffect } from "react";
import { notFound, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {
  Heart,
  Share2,
  Truck,
  ShieldCheck,
  RotateCcw,
  ChevronRight,
  Minus,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProductCard } from "@/components/ui/product-card";
import { FabricPreview } from "@/components/ui/fabric-preview";
import { formatPrice, type Product } from "@/lib/data";
import { useCatalog } from "@/lib/context/catalog-context";
import { useCart } from "@/lib/context/cart-context";
import { useWishlist } from "@/lib/context/wishlist-context";
import { useToast } from "@/lib/context/toast-context";
import { WhatsAppAction } from "@/components/whatsapp/whatsapp-action";
import { trackProductEvent } from "@/lib/analytics";
import { useAnalyticsChoice } from "@/components/analytics/analytics-controls";
import { productEnquiry } from "@/lib/whatsapp";
import { isStaticStorefront } from "@/lib/storefront-mode";
import { ProductReviews } from "@/components/reviews/product-reviews";

export default function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const { products, mode, error, retry } = useCatalog();
  const product = products.find((p) => p.slug === slug);

  if (mode === "loading") return <div className="container-page py-20" role="status">Loading product…</div>;
  if (mode === "error") return <div className="container-page py-20" role="alert"><p>{error}</p><button onClick={retry} className="mt-4 underline">Retry</button></div>;

  if (!product) {
    notFound();
  }

  return <ProductDetail key={product.id} product={product} products={products} />;
}

function ProductDetail({ product, products }: { product: Product; products: Product[] }) {
  const router = useRouter();
  const { mode } = useCatalog();

  const [selectedVariantId, setSelectedVariantId] = useState(product.variants.find((variant) => variant.stock > 0)?.id || product.variants[0]?.id || "");
  const [quantity, setQuantity] = useState(1);
  const [showPhoto, setShowPhoto] = useState(true);

  // Cart & Wishlist
  const { addItem } = useCart();
  const { isWishlisted, toggle: toggleWishlist } = useWishlist();
  const { addToast } = useToast();
  const wishlisted = isWishlisted(product.slug);

  const selectedVariant = product.variants.find(
    (v) => v.id === selectedVariantId
  );
  const analyticsChoice = useAnalyticsChoice();
  useEffect(() => {
    if (selectedVariant && analyticsChoice === "accepted") trackProductEvent("view_item", product, selectedVariant, 1);
  }, [product, selectedVariant, analyticsChoice]);
  const currentPrice = selectedVariant?.salePrice ?? selectedVariant?.price ?? 0;
  const originalPrice = selectedVariant?.price ?? 0;
  const hasSale = currentPrice < originalPrice;
  const isOutOfStock = (selectedVariant?.stock ?? 0) === 0;

  const relatedProducts = products
    .filter((p) => p.id !== product.id && p.category === product.category)
    .slice(0, 4);

  return (
    <div className="bg-cream">
      {/* Breadcrumb */}
      <div className="container-page py-4">
        <nav className="flex items-center gap-2 text-sm text-charcoal/75">
          <Link href="/" className="hover:text-charcoal transition-colors">
            Home
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <Link href="/shop" className="hover:text-charcoal transition-colors">
            Shop
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="text-charcoal/70 truncate">{product.title}</span>
        </nav>
      </div>

      <div className="container-page pb-20">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 md:gap-12">
          {/* -------- PRODUCT IMAGES -------- */}
          <div className="min-w-0 space-y-4">
            {/* Main Image */}
            <div className="relative aspect-[3/4] rounded-2xl overflow-hidden border border-[#d9cbc2] bg-warm-cream">
              {showPhoto ? (
                <>
                  <Image src={product.displayImage} alt={product.displayImageAlt} fill preload loading="eager" sizes="(max-width: 768px) 100vw, 45vw" className="object-cover object-center" />
                  <span className="absolute bottom-4 right-4 rounded-full bg-cream/95 px-3 py-1.5 text-xs font-medium text-charcoal shadow-sm">{product.displayImageKind === "brand" ? "Collection photo" : product.displayImageKind === "illustration" ? "Illustrative image" : "Style reference"}</span>
                </>
              ) : (
                <FabricPreview color={selectedVariant?.colorHex || "#D4C5B9"} name={selectedVariant?.name || product.title} className="h-full w-full" />
              )}

              {/* Badges */}
              <div className="absolute top-4 left-4 flex flex-col gap-1.5">
                {product.isNew && <Badge variant="new">New</Badge>}
                {product.isBestSeller && (
                  <Badge variant="bestseller">Featured</Badge>
                )}
                {hasSale && <Badge variant="sale">Sale</Badge>}
                {isOutOfStock && <Badge variant="outOfStock">Sold Out</Badge>}
              </div>

              {/* Wishlist & Share */}
              <div className="absolute top-4 right-4 flex flex-col gap-2">
                <button
                  onClick={() => {
                    toggleWishlist(product.slug);
                    if (!wishlisted) {
                      addToast({
                        type: "wishlist",
                        message: `${product.title} saved to wishlist`,
                        actionLabel: "View",
                        actionHref: "/wishlist",
                      });
                    }
                  }}
                  className={`p-2.5 rounded-xl transition-all ${
                    wishlisted
                      ? "bg-dusty-rose text-cream shadow-lg shadow-dusty-rose/20"
                      : "bg-cream/80 backdrop-blur-sm text-charcoal/75 hover:text-dusty-rose hover:bg-cream"
                  }`}
                  aria-label={wishlisted ? `Remove ${product.title} from wishlist` : `Add ${product.title} to wishlist`}
                >
                  <Heart
                    className="w-4 h-4"
                    fill={wishlisted ? "currentColor" : "none"}
                  />
                </button>
                <button onClick={async () => { if (navigator.share) { await navigator.share({ title: product.title, url: window.location.href }).catch(() => undefined); } else { await navigator.clipboard.writeText(window.location.href); addToast({ type: "success", message: "Product link copied" }); } }} className="p-2.5 rounded-xl bg-cream/80 backdrop-blur-sm text-charcoal/75 hover:text-charcoal transition-all" aria-label={`Share ${product.title}`}>
                  <Share2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="text-xs leading-relaxed text-charcoal/75">
              <p>{showPhoto ? `${product.displayImageNote}. Select a shade below to see its illustrated colour preview.` : "Illustrated colour preview. Select the photo thumbnail to view the styling reference again."}</p>
              {product.imageCredit && <p className="mt-1">Photo by <a href={product.imageCredit.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-charcoal">{product.imageCredit.creator}</a> · <a href={product.imageCredit.licenseUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-charcoal">{product.imageCredit.license}</a>{product.imageCredit.license === "CC BY-SA 3.0" ? " · display crop" : ""}</p>}
            </div>

            {/* Variant color thumbnails */}
            <div className="flex gap-3 overflow-x-auto pb-2">
              <button type="button" onClick={() => setShowPhoto(true)} className={`relative h-20 w-16 flex-shrink-0 overflow-hidden rounded-xl border-2 transition-all ${showPhoto ? "border-charcoal shadow-md" : "border-transparent hover:border-sand"}`} aria-label={product.displayImageKind === "brand" ? "View collection photo" : product.displayImageKind === "illustration" ? "View illustrative image" : "View style reference photo"} aria-pressed={showPhoto}>
                <Image src={product.displayImage} alt="" fill loading="eager" sizes="64px" className="object-cover object-center" />
              </button>
              {product.variants.map((variant) => (
                <button
                  key={variant.id}
                  onClick={() => {
                    setSelectedVariantId(variant.id);
                    setQuantity(1);
                    setShowPhoto(false);
                  }}
                  className={`flex-shrink-0 w-16 h-20 rounded-xl overflow-hidden border-2 transition-all ${
                    !showPhoto && selectedVariantId === variant.id
                      ? "border-charcoal shadow-md"
                      : "border-transparent hover:border-sand"
                  } ${variant.stock === 0 ? "opacity-40" : ""}`}
                  aria-label={`Preview ${variant.name}${variant.stock === 0 ? ", out of stock" : ""}`}
                  aria-pressed={!showPhoto && selectedVariantId === variant.id}
                >
                  <div
                    className="w-full h-full"
                    style={{ backgroundColor: variant.colorHex }}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* -------- PRODUCT DETAILS -------- */}
          <div className="min-w-0 space-y-6">
            {/* Title */}
            <div>
              <p className="label-text text-terracotta mb-2">{product.fabric}</p>
              <h1 className="heading-lg text-charcoal mb-2">{product.title}</h1>
              <p className="text-sm text-charcoal/75">Available in {product.variants.length} {product.variants.length === 1 ? "shade" : "shades"}</p>
            </div>

            {/* Price */}
            <div className="flex items-baseline gap-3">
              <span className="text-2xl font-medium text-charcoal">
                {formatPrice(currentPrice)}
              </span>
              {hasSale && (
                <>
                  <span className="text-lg text-charcoal/75 line-through">
                    {formatPrice(originalPrice)}
                  </span>
                  <span className="text-sm font-medium text-rust bg-rust/10 px-2 py-0.5 rounded-full">
                    Save {formatPrice(originalPrice - currentPrice)}
                  </span>
                </>
              )}
            </div>

            {/* Selected variant info */}
            <p className="text-sm text-charcoal/75">
              Selected:{" "}
              <span className="font-medium text-charcoal">
                {selectedVariant?.name}
              </span>
              {selectedVariant && (
                <span className="ml-2">
                  {isOutOfStock ? (
                    <span className="text-rust font-medium">— Out of Stock</span>
                  ) : selectedVariant.stock <= 5 ? (
                    <span className="text-gold font-medium">
                      — Only {selectedVariant.stock} left
                    </span>
                  ) : null}
                </span>
              )}
            </p>

            {/* Color/Variant Selector */}
            <div>
              <p className="text-sm font-medium text-charcoal mb-3">
                Color: <span className="text-charcoal/75">{selectedVariant?.name}</span>
              </p>
              <div className="flex flex-wrap gap-3">
                {product.variants.map((variant) => (
                  <button
                    key={variant.id}
                    onClick={() => { setSelectedVariantId(variant.id); setQuantity(1); setShowPhoto(false); }}
                    disabled={variant.stock === 0}
                    className={`group relative w-10 h-10 rounded-full transition-all ${
                      selectedVariantId === variant.id
                        ? "ring-2 ring-charcoal ring-offset-2 scale-110"
                        : "hover:scale-105"
                    } ${variant.stock === 0 ? "opacity-30 cursor-not-allowed" : ""}`}
                    title={`${variant.name}${variant.stock === 0 ? " — Out of Stock" : ""}`}
                    aria-label={`${variant.name}${variant.stock === 0 ? " — Out of Stock" : ""}`}
                    aria-pressed={selectedVariantId === variant.id}
                  >
                    <div
                      className="w-full h-full rounded-full border border-sand/50"
                      style={{ backgroundColor: variant.colorHex }}
                    />
                    {variant.stock === 0 && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-[2px] h-full bg-charcoal/30 rotate-45 absolute" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Quantity */}
            <div>
              <p className="text-sm font-medium text-charcoal mb-3">Quantity</p>
              <div className="flex items-center gap-0 border border-sand rounded-xl w-fit">
                <button
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  disabled={quantity <= 1}
                  aria-label="Decrease quantity"
                  className="p-3 text-charcoal/75 hover:text-charcoal disabled:opacity-30 transition-colors"
                >
                  <Minus className="w-4 h-4" />
                </button>
                <span className="w-12 text-center text-sm font-medium text-charcoal select-none">
                  {quantity}
                </span>
                <button
                  onClick={() =>
                    setQuantity(
                      Math.min(selectedVariant?.stock ?? 99, quantity + 1)
                    )
                  }
                  disabled={quantity >= (selectedVariant?.stock ?? 99)}
                  aria-label="Increase quantity"
                  className="p-3 text-charcoal/75 hover:text-charcoal disabled:opacity-30 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Actions */}
            <div className="flex min-w-0 gap-3 pt-2">
              <Button
                variant="primary"
                size="md"
                className="min-w-0 flex-1"
                disabled={isOutOfStock}
                onClick={async () => {
                  if (!isOutOfStock && selectedVariant) {
                    if (!await addItem(selectedVariant.id, product.slug, quantity)) return;
                    addToast({
                      type: "cart",
                      message: `${product.title} — ${selectedVariant.name} × ${quantity} added`,
                      actionLabel: "View Cart",
                      actionHref: "/cart",
                    });
                  }
                }}
              >
                {isOutOfStock ? "Sold Out" : "Add to Cart"}
              </Button>
              <Button
                variant="outline"
                size="md"
                className="min-w-0 flex-1"
                disabled={isOutOfStock}
                onClick={async () => {
                  if (!isOutOfStock && selectedVariant) {
                    if (!await addItem(selectedVariant.id, product.slug, quantity)) return;
                    router.push("/cart");
                  }
                }}
              >
                Buy Now
              </Button>
            </div>

            {mode === "live" && selectedVariant && <WhatsAppAction label="Enquire about this product on WhatsApp" message={(origin) => productEnquiry(product, selectedVariant, origin, quantity)} />}

            {/* Delivery Info */}
            <div className="grid grid-cols-3 gap-3 pt-4">
              {[
                { icon: Truck, text: mode === "live" ? "Delivery confirmed in chat" : "Delivery details coming soon" },
                { icon: ShieldCheck, text: mode === "live" ? "Payment discussed in chat" : "Ordering not yet open" },
                { icon: RotateCcw, text: mode === "live" ? "Order confirmed in chat" : "Return policy coming soon" },
              ].map((item) => (
                <div
                  key={item.text}
                  className="flex flex-col items-center text-center gap-1.5 p-3 rounded-xl bg-warm-cream"
                >
                  <item.icon className="w-4 h-4 text-terracotta/60" />
                  <span className="text-[10px] leading-tight text-charcoal/75">
                    {item.text}
                  </span>
                </div>
              ))}
            </div>

            {/* Description */}
            <div className="pt-4 border-t border-sand/50 space-y-4">
              <div>
                <h2 className="text-sm font-medium text-charcoal mb-2">
                  Description
                </h2>
                <p className="text-sm text-charcoal/75 leading-relaxed">
                  {product.description}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-charcoal mb-1">
                    Fabric
                  </h3>
                  <p className="text-sm text-charcoal/75">{product.fabric}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-charcoal mb-1">
                    Dimensions
                  </h3>
                  <p className="text-sm text-charcoal/75">{product.dimensions}</p>
                </div>
                <div className="col-span-2">
                  <h3 className="text-sm font-medium text-charcoal mb-1">
                    Care Instructions
                  </h3>
                  <p className="text-sm text-charcoal/75">{product.care}</p>
                </div>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-2">
                {product.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 text-xs bg-warm-cream text-charcoal/75 rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* -------- RELATED PRODUCTS -------- */}
        {relatedProducts.length > 0 && (
          <section className="mt-20 pt-16 border-t border-sand/50">
            <div className="flex items-center justify-between mb-8">
              <div>
                <p className="label-text text-terracotta mb-2">You May Also Like</p>
                <h2 className="heading-md text-charcoal">Related Products</h2>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
              {relatedProducts.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          </section>
        )}
        {!isStaticStorefront() && <ProductReviews key={product.slug} slug={product.slug} />}
      </div>
    </div>
  );
}
