"use client";

import { useEffect } from "react";
import { useAnalyticsChoice } from "@/components/analytics/analytics-controls";
import { trackEvent } from "@/lib/analytics";
import Link from "next/link";
import {
  Trash2,
  Heart,
  ArrowLeft,
  Minus,
  Plus,
  ShoppingBag,
  ChevronRight,
} from "lucide-react";
import { WhatsAppAction } from "@/components/whatsapp/whatsapp-action";
import { cartEnquiry, type EnquiryLine } from "@/lib/whatsapp";
import { useCart } from "@/lib/context/cart-context";
import { useWishlist } from "@/lib/context/wishlist-context";
import { useToast } from "@/lib/context/toast-context";
import { useCatalog } from "@/lib/context/catalog-context";

export default function CartPage() {
  const {
    items,
    itemCount,
    subtotal,
    updateQuantity,
    removeItem,
    getAllLines,
    formatPrice: fmtPrice,
    loading,
    error,
    refreshCart,
  } = useCart();
  const { mode } = useCatalog();
  const { add: addToWishlist, isWishlisted } = useWishlist();
  const { addToast } = useToast();

  const analyticsChoice = useAnalyticsChoice();
  useEffect(() => {
    if (!loading && items.length && analyticsChoice === "accepted") trackEvent("view_cart", { currency: "PKR", value: subtotal, item_count: itemCount });
  }, [loading, itemCount, items.length, subtotal, analyticsChoice]);
  const lines = getAllLines();
  const incomplete = lines.length !== items.length || lines.some((line) => !line.product || !line.variant);

  const handleRemove = async (lineId: string, productTitle?: string) => {
    if (await removeItem(lineId) && productTitle) {
      addToast({
        type: "cart",
        message: `${productTitle} removed from cart`,
      });
    }
  };

  const handleMoveToWishlist = async (lineId: string, productSlug?: string) => {
    if (!await removeItem(lineId)) return;
    if (productSlug && !isWishlisted(productSlug)) {
      addToWishlist(productSlug);
      addToast({
        type: "wishlist",
        message: "Item saved to wishlist",
        actionLabel: "View",
        actionHref: "/wishlist",
      });
    }
  };

  if (loading) return <div className="container-page py-20" role="status">Loading cart…</div>;

  if (items.length === 0) {
    return (
      <div className="min-h-[70vh] flex items-center bg-cream">
        <div className="container-page text-center py-20">
          {error && <div role="alert" className="mx-auto mb-6 max-w-md rounded-xl bg-rust/10 p-4 text-rust">{error} <button type="button" onClick={() => void refreshCart()} className="underline">Retry</button></div>}
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-warm-cream mb-6">
            <ShoppingBag className="w-8 h-8 text-charcoal/60" />
          </div>
          <h2 className="heading-md text-charcoal mb-3">Your cart is empty</h2>
          <p className="text-charcoal/75 mb-8 max-w-md mx-auto">
            Looks like you haven&apos;t added anything yet. Browse our
            collection and find something you&apos;ll love.
          </p>
          <Link href="/shop" className="inline-flex items-center justify-center rounded-xl bg-charcoal px-8 py-4 text-base font-medium text-cream hover:bg-ink">Continue Shopping</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-cream min-h-screen">
      <div className="container-page py-8 md:py-12">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-charcoal/75 mb-8">
          <Link href="/" className="hover:text-charcoal transition-colors">
            Home
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="text-charcoal/70">Cart</span>
        </nav>

        <h1 className="heading-lg text-charcoal mb-2">Shopping Cart</h1>
        {error && <div role="alert" className="mb-5 rounded-xl bg-rust/10 p-4 text-rust">{error} <button type="button" onClick={() => void refreshCart()} className="underline">Retry</button></div>}
        <p className="text-charcoal/75 mb-10">
          {itemCount} {itemCount === 1 ? "item" : "items"} in your cart
        </p>

        <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
          {/* Cart Items */}
          <div className="min-w-0 space-y-4 lg:col-span-2">
            {lines.map((line) => (
              <div
                key={line.lineId}
                className="flex min-w-0 gap-4 p-4 md:p-5 bg-white rounded-2xl border border-sand/50 animate-fade-in-up"
              >
                {/* Product Image */}
                <div className="w-20 h-28 flex-shrink-0 rounded-xl overflow-hidden bg-warm-cream md:w-28 md:h-36">
                  <div
                    className="w-full h-full"
                    style={{
                      background: `linear-gradient(135deg, ${line.variant?.colorHex || "#D4C5B9"}40, ${line.variant?.colorHex || "#D4C5B9"}10)`,
                    }}
                  />
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:justify-between sm:gap-2">
                    <div className="min-w-0 flex-1">
                      <Link
                        href={line.product ? `/shop/${line.product.slug}` : "/shop"}
                        className="font-medium text-charcoal hover:text-terracotta transition-colors line-clamp-2 sm:line-clamp-1"
                      >
                        {line.product?.title || "Unavailable product"}
                      </Link>
                      <p className="text-sm text-charcoal/75 mt-0.5">
                        Color: {line.variant?.name}
                      </p>
                      <p className="text-xs text-charcoal/75 mt-0.5">
                        {line.product?.fabric}
                      </p>
                    </div>

                    {/* Price */}
                    <div className="flex-shrink-0 text-left sm:text-right">
                      <p className="font-medium text-charcoal">
                        {fmtPrice(line.lineTotal)}
                      </p>
                      {(line.variant?.salePrice ?? 0) <
                        (line.variant?.price ?? 0) && (
                        <p className="text-xs text-charcoal/75 line-through">
                          {fmtPrice((line.variant?.price ?? 0) * line.quantity)}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Stock info */}
                  {line.variant && line.variant.stock <= 5 && line.variant.stock > 0 && (
                    <p className="text-xs text-gold mt-1">
                      Only {line.variant.stock} left in stock
                    </p>
                  )}

                  {/* Actions Row */}
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-x-2 gap-y-2">
                    {/* Quantity */}
                    <div className="flex items-center border border-sand rounded-lg">
                      <button
                        type="button"
                        aria-label={`Decrease quantity of ${line.product?.title ?? "item"}`}
                        onClick={() =>
                          updateQuantity(line.lineId, line.quantity - 1)
                        }
                        disabled={line.quantity <= 1}
                        className="p-2 text-charcoal/75 hover:text-charcoal disabled:opacity-30 transition-colors"
                      >
                        <Minus className="w-3.5 h-3.5" />
                      </button>
                      <span className="w-10 text-center text-sm font-medium text-charcoal select-none">
                        {line.quantity}
                      </span>
                      <button
                        type="button"
                        aria-label={`Increase quantity of ${line.product?.title ?? "item"}`}
                        onClick={() =>
                          updateQuantity(line.lineId, line.quantity + 1)
                        }
                        disabled={line.quantity >= (line.variant?.stock ?? 99)}
                        className="p-2 text-charcoal/75 hover:text-charcoal disabled:opacity-30 transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          handleMoveToWishlist(
                            line.lineId,
                            line.product?.slug
                          )
                        }
                        className="p-2 text-charcoal/75 hover:text-dusty-rose transition-colors rounded-lg"
                        title="Move to wishlist"
                      >
                        <Heart className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() =>
                          handleRemove(line.lineId, line.product?.title)
                        }
                        className="p-2 text-charcoal/75 hover:text-rust transition-colors rounded-lg"
                        title="Remove from cart"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            <div className="pt-4">
              <Link
                href="/shop"
                className="inline-flex items-center gap-1 text-sm text-charcoal/75 hover:text-terracotta transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Continue Shopping
              </Link>
            </div>
          </div>

          {/* Order Summary */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl border border-sand/50 p-6 sticky top-24 space-y-5">
              <h3 className="font-medium text-charcoal">Order Summary</h3>

              <div className="flex justify-between text-sm">
                <span className="text-charcoal/75">Estimated subtotal ({itemCount} items)</span>
                <span className="font-medium text-charcoal">{incomplete ? "Unavailable" : fmtPrice(subtotal)}</span>
              </div>
              <p className="text-sm text-charcoal/75">Availability, prices, delivery and payment will be confirmed in chat. Your request is not a confirmed order.</p>
              {mode !== "live" ? <p role="status" className="text-sm text-charcoal/75">Ordering is unavailable while the catalogue is in preview.</p> : incomplete ? <p role="alert" className="text-sm text-rust">Some product details are unavailable. Remove the unavailable items or retry before ordering.</p> : <WhatsAppAction key={JSON.stringify(lines)} label="Order via WhatsApp" disabled={Boolean(error)} message={(origin) => cartEnquiry(lines as EnquiryLine[], subtotal, origin, fmtPrice)} />}
              <p className="text-xs text-charcoal/75">Your cart stays here after you open WhatsApp. Please send the message to start your enquiry.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
