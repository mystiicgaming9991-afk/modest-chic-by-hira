"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ShoppingBag } from "lucide-react";
import { formatPrice } from "@/lib/data";

interface Order {
  order_number: string;
  state: string;
  payment_state: string;
  total_minor: number;
  items: Array<{ id: string; product_title: string; variant_name: string; quantity: number; line_total_minor: number; review_eligible: boolean }>;
  events: Array<{ label: string; occurred_at: string }>;
}

export function ConfirmationClient({ orderId }: { orderId: string | null }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(orderId));
  const [claimMessage, setClaimMessage] = useState("");
  const [claiming, setClaiming] = useState(false);

  async function claimOrder() {
    if (!orderId) return;
    setClaiming(true);
    try {
      const response = await fetch(`/api/customer/orders/${encodeURIComponent(orderId)}/claim`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message ?? "Could not save this order.");
      setClaimMessage("Saved to your account. You can see it in your order history.");
    } catch (cause) {
      setClaimMessage(cause instanceof Error ? cause.message : "Could not save this order.");
    } finally { setClaiming(false); }
  }

  useEffect(() => {
    if (!orderId) return;
    let active = true;
    fetch(`/api/commerce/orders/${encodeURIComponent(orderId)}`, { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.message ?? "Order unavailable.");
        return body as Order;
      })
      .then((result) => { if (active) setOrder(result); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Order unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [orderId]);

  return (
    <div className="min-h-[60vh] bg-cream">
      <div className="container-page mx-auto max-w-2xl py-20 text-center">
        <span className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-warm-cream text-terracotta"><ShoppingBag className="h-7 w-7" /></span>
        {loading ? <p role="status">Loading your order…</p> : order ? <>
          <h1 className="heading-lg mb-4 text-charcoal">Thank you for your order</h1>
          <p className="text-charcoal/75">Order {order.order_number} · {order.state.replaceAll("_", " ").toLowerCase()}</p>
          <div className="mt-8 rounded-2xl border border-sand bg-white p-6 text-left">
            {order.items.map((item) => <div key={item.id} className="border-b border-sand/50 py-3 text-sm last:border-0"><div className="flex justify-between gap-4"><span>{item.product_title} · {item.variant_name} × {item.quantity}</span><span>{formatPrice(item.line_total_minor / 100)}</span></div>{orderId && item.review_eligible && <OrderReviewForm orderId={orderId} orderItemId={item.id} productTitle={item.product_title} />}</div>)}
            <div className="flex justify-between pt-4 font-medium"><span>Total</span><span>{formatPrice(order.total_minor / 100)}</span></div>
          </div>
          {order.events.length > 0 && <section aria-labelledby="order-progress" className="mt-6 rounded-2xl border border-sand bg-white p-6 text-left"><h2 id="order-progress" className="font-medium text-charcoal">Order progress</h2><ol className="mt-4 space-y-4">{order.events.map((event, index) => <li key={`${event.occurred_at}:${index}`} className="flex gap-3 text-sm"><span aria-hidden="true" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-terracotta" /><div><p className="text-charcoal">{event.label}</p><time dateTime={event.occurred_at} className="text-xs text-charcoal/75">{new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" }).format(new Date(event.occurred_at))} PKT</time></div></li>)}</ol></section>}
          <p className="mt-5 text-sm text-charcoal/75">Keep this page in this browser to check your order progress.</p>
          <div className="mt-5"><button disabled={claiming} onClick={() => void claimOrder()} className="rounded-full border border-charcoal px-5 py-2 text-sm text-charcoal disabled:opacity-50">Save this order to my account</button><p className="mt-2 text-xs text-charcoal/75">Sign in from <Link href="/account" className="underline">your account</Link> first. You must use the browser that placed this order.</p>{claimMessage && <p role="status" className="mt-2 text-sm">{claimMessage}</p>}</div>
        </> : <>
          <h1 className="heading-lg mb-4 text-charcoal">Order details unavailable</h1>
          <p role="alert" className="text-charcoal/75">{error ?? "No order was selected. Orders placed from this browser can be opened from their confirmation link."}</p>
        </>}
        <Link href="/shop" className="mt-8 inline-flex items-center gap-2 rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-cream hover:bg-deep-rust">Continue shopping <ArrowRight className="h-4 w-4" /></Link>
      </div>
    </div>
  );
}

function OrderReviewForm({ orderId, orderItemId, productTitle }: { orderId: string; orderItemId: string; productTitle: string }) {
  const [rating, setRating] = useState("5");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`/api/customer/orders/${encodeURIComponent(orderId)}/reviews`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_item_id: orderItemId, rating: Number(rating), title, body }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Review could not be submitted.");
      setMessage("Thank you. Your review is awaiting moderation.");
      setSubmitted(true);
      setTitle(""); setBody("");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Review could not be submitted.");
    } finally { setBusy(false); }
  }

  return <form onSubmit={(event) => void submit(event)} className="mt-3 rounded-xl bg-cream p-4">
    <h3 className="font-medium text-charcoal">Review {productTitle}</h3>
    <div className="mt-3 grid gap-3 sm:grid-cols-[8rem_1fr]">
      <label className="text-xs font-medium">Rating<select aria-label={`Rating for ${productTitle}`} value={rating} onChange={(event) => setRating(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2">{[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{value} / 5</option>)}</select></label>
      <label className="text-xs font-medium">Title (optional)<input maxLength={255} value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2" /></label>
    </div>
    <label className="mt-3 block text-xs font-medium">Your review (optional)<textarea maxLength={5000} rows={3} value={body} onChange={(event) => setBody(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2" /></label>
    <div className="mt-3 flex flex-wrap items-center gap-3"><button disabled={busy || submitted} className="rounded-full bg-charcoal px-4 py-2 text-xs font-medium text-white disabled:opacity-50">{busy ? "Submitting…" : submitted ? "Submitted" : "Submit review"}</button><p aria-live="polite" className="text-xs text-charcoal/75">{message}</p></div>
  </form>;
}
