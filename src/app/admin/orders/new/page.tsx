"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";

interface Product { id: string; title: string; status: string }
interface Variant { id: string; sku: string; color_name: string; price_minor: number; sale_price_minor: number | null; is_active: boolean }
interface ProductDetail extends Product { variants: Variant[] }
interface ProductList { items: Product[]; next_cursor: string | null }
interface ManualOptions { delivery_cities: string[]; pickup_cities: string[]; delivery_fee_minor: number | null; payment_methods: string[] }
interface ManualLine { variant: Variant; quantity: number }
interface CreatedOrder { order_id: string; order_number: string; source: string; state: string; total_minor: number; replayed: boolean }

export default function ManualOrderPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsCursor, setProductsCursor] = useState<string | null>(null);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [options, setOptions] = useState<ManualOptions>({ delivery_cities: [], pickup_cities: [], delivery_fee_minor: null, payment_methods: [] });
  const [variants, setVariants] = useState<Variant[]>([]);
  const [productId, setProductId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [lines, setLines] = useState<ManualLine[]>([]);
  const [source, setSource] = useState<"MANUAL" | "SOCIAL">("SOCIAL");
  const [fulfillment, setFulfillment] = useState<"DELIVERY" | "PICKUP">("DELIVERY");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [attributionSource, setAttributionSource] = useState("Instagram");
  const [campaign, setCampaign] = useState("");
  const [creatorCode, setCreatorCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedOrder | null>(null);
  const orderRetry = useRef<{ fingerprint: string; key: string; uncertain: boolean } | null>(null);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      Promise.all([
        staffJson<StaffIdentity>("auth/me"),
        staffJson<ProductList>("admin/catalog/products?limit=100&status=PUBLISHED"),
        staffJson<ManualOptions>("admin/orders/manual/options"),
      ]).then(([user, result, manualOptions]) => {
        if (!active) return;
        setIdentity(user); setProducts(result.items); setProductsCursor(result.next_cursor); setOptions(manualOptions);
      }).catch((cause) => {
        if (active) {
          const status = cause instanceof Error && typeof (cause as Error & { status?: unknown }).status === "number"
            ? (cause as Error & { status: number }).status
            : null;
          if (status === 401) router.replace("/admin/login");
          else setError(cause instanceof Error ? cause.message : "Order form could not be loaded.");
        }
      }).finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function loadMoreProducts() {
    if (!productsCursor || loadingProducts) return;
    setLoadingProducts(true); setError(null);
    try {
      const page = await staffJson<ProductList>(
        `admin/catalog/products?limit=100&status=PUBLISHED&after=${encodeURIComponent(productsCursor)}`,
      );
      setProducts((current) => [...current, ...page.items]);
      setProductsCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "More products could not be loaded.");
    } finally { setLoadingProducts(false); }
  }

  useEffect(() => {
    if (!productId) return;
    let active = true;
    staffJson<ProductDetail>(`admin/catalog/products/${productId}`).then((product) => {
      if (active) { setVariants(product.variants.filter((variant) => variant.is_active)); setVariantId(""); }
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Variants could not be loaded."); });
    return () => { active = false; };
  }, [productId]);

  function addLine() {
    const variant = variants.find((item) => item.id === variantId);
    const count = Number(quantity);
    const existingQuantity = lines.find((line) => line.variant.id === variantId)?.quantity ?? 0;
    if (!variant || !Number.isInteger(count) || count < 1 || count > 1000 || existingQuantity + count > 1000) return;
    setLines((current) => {
      const existing = current.find((line) => line.variant.id === variant.id);
      return existing
        ? current.map((line) => line.variant.id === variant.id ? { ...line, quantity: line.quantity + count } : line)
        : [...current, { variant, quantity: count }];
    });
    setVariantId(""); setQuantity("1"); setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setCreated(null);
    let requestFingerprint = "";
    try {
      const request = {
        source, customer_name: customerName,
        customer_phone: customerPhone, customer_email: customerEmail || null,
        items: lines.map(({ variant, quantity: count }) => ({ variant_id: variant.id, quantity: count })),
        fulfillment_method: fulfillment, city, address_line1: fulfillment === "DELIVERY" ? address : null,
        attribution_source: attributionSource || null, attribution_campaign: campaign || null,
        attribution_creator_code: creatorCode || null,
      };
      requestFingerprint = JSON.stringify(request);
      const pending = orderRetry.current;
      if (pending?.uncertain && pending.fingerprint !== requestFingerprint) {
        throw new Error("The previous order request may have been accepted. Restore its details and retry before starting another order.");
      }
      const key = pending?.fingerprint === requestFingerprint ? pending.key : crypto.randomUUID();
      orderRetry.current = { fingerprint: requestFingerprint, key, uncertain: false };
      const result = await staffJson<CreatedOrder>("admin/orders/manual", jsonBody({ ...request, idempotency_key: key }));
      orderRetry.current = null;
      setCreated(result); setLines([]);
    } catch (cause) {
      const status = cause instanceof Error && typeof (cause as Error & { status?: unknown }).status === "number"
        ? (cause as Error & { status: number }).status
        : null;
      const pending = orderRetry.current;
      if (status !== null && status < 500) orderRetry.current = null;
      else if (pending) orderRetry.current = { ...pending, uncertain: true };
      const message = cause instanceof Error ? cause.message : "Order could not be recorded.";
      setError(pending && (status === null || status >= 500) && pending.fingerprint === requestFingerprint
        ? "The order request may have been accepted. Retry without changing the order details before starting another order."
        : message);
    }
    finally { setBusy(false); }
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("order.create_manual")) return <p role="alert">Manual order creation is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  const selectedVariant = variants.find((variant) => variant.id === variantId);
  const merchandiseTotal = lines.reduce((total, line) => total + (line.variant.sale_price_minor ?? line.variant.price_minor) * line.quantity, 0);
  const availableCities = fulfillment === "DELIVERY" ? options.delivery_cities : options.pickup_cities;

  return <div className="mx-auto max-w-4xl space-y-8">
    <header><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Record a manual order</h1><p className="mt-2 text-sm text-charcoal/75">Current published prices and available stock are rechecked when you save. Only configured COD and fulfillment options can be accepted.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {created && <p role="status" className="rounded-lg bg-warm-cream p-4">Order <strong>{created.order_number}</strong> recorded ({created.state.toLowerCase()}) for PKR {(created.total_minor / 100).toFixed(2)}.{created.replayed ? " This was an idempotent replay." : ""}</p>}
    <form onSubmit={(event) => void submit(event)}>
      <fieldset disabled={busy} className="space-y-6 rounded-2xl border border-sand bg-white p-6">
      <section className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Source<select value={source} onChange={(event) => setSource(event.target.value as "MANUAL" | "SOCIAL")} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="SOCIAL">Social channel</option><option value="MANUAL">Manual sale</option></select></label>
        <label className="text-sm font-medium">Fulfillment<select value={fulfillment} onChange={(event) => { setFulfillment(event.target.value as "DELIVERY" | "PICKUP"); setCity(""); }} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="DELIVERY">Delivery</option><option value="PICKUP">Pickup</option></select></label>
        <label className="text-sm font-medium">Customer name<input required maxLength={255} value={customerName} onChange={(event) => setCustomerName(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Phone<input required maxLength={30} value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Email (optional)<input type="email" maxLength={255} value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">City<select required value={city} onChange={(event) => setCity(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">Choose a configured city</option>{availableCities.map((name) => <option key={name}>{name}</option>)}</select></label>
        {fulfillment === "DELIVERY" && <label className="text-sm font-medium sm:col-span-2">Delivery address<input required maxLength={500} value={address} onChange={(event) => setAddress(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>}
      </section>
      <section className="space-y-3 border-t border-sand pt-5"><h2 className="font-medium">Items</h2><div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_7rem_auto]">
        <label className="text-sm font-medium">Product<select value={productId} onChange={(event) => { setProductId(event.target.value); setVariants([]); setVariantId(""); }} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">Choose product</option>{products.map((product) => <option value={product.id} key={product.id}>{product.title}</option>)}</select></label>
        <label className="text-sm font-medium">Variant<select value={variantId} onChange={(event) => setVariantId(event.target.value)} disabled={!variants.length} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">Choose variant</option>{variants.map((variant) => <option value={variant.id} key={variant.id}>{variant.color_name} · {variant.sku} · PKR {((variant.sale_price_minor ?? variant.price_minor) / 100).toFixed(2)}</option>)}</select></label>
        <label className="text-sm font-medium">Qty<input type="number" min="1" max="1000" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <button type="button" disabled={!selectedVariant || !Number.isInteger(Number(quantity)) || Number(quantity) < 1 || Number(quantity) > 1000 || (lines.find((line) => line.variant.id === variantId)?.quantity ?? 0) + Number(quantity) > 1000} onClick={addLine} className="rounded-lg border border-sand px-4 py-3 text-sm disabled:opacity-50">Add item</button>
      </div>
      {productsCursor && <button type="button" disabled={busy || loadingProducts} onClick={() => void loadMoreProducts()} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-50">{loadingProducts ? "Loading products…" : "Load more products"}</button>}
      {lines.length > 0 ? <ul className="divide-y divide-sand">{lines.map(({ variant, quantity: count }) => <li key={variant.id} className="flex items-center justify-between gap-3 py-3 text-sm"><span>{variant.sku} · {variant.color_name} × {count}</span><span>PKR {(((variant.sale_price_minor ?? variant.price_minor) * count) / 100).toFixed(2)} <button type="button" onClick={() => setLines((current) => current.filter((line) => line.variant.id !== variant.id))} className="ml-3 text-terracotta underline">Remove</button></span></li>)}</ul> : <p className="text-sm text-charcoal/75">No items added yet.</p>}
      {lines.length > 0 && <p className="text-right text-sm font-medium">Merchandise subtotal: PKR {(merchandiseTotal / 100).toFixed(2)}{fulfillment === "DELIVERY" && options.delivery_fee_minor !== null && <> · Delivery PKR {(options.delivery_fee_minor / 100).toFixed(2)}</>}</p>}</section>
      <section className="grid gap-4 border-t border-sand pt-5 sm:grid-cols-3"><label className="text-sm font-medium">Sales channel<input value={attributionSource} onChange={(event) => setAttributionSource(event.target.value)} placeholder="Instagram" className="mt-1 block w-full rounded-lg border border-sand p-3" /></label><label className="text-sm font-medium">Campaign<input value={campaign} onChange={(event) => setCampaign(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label><label className="text-sm font-medium">Creator code<input value={creatorCode} onChange={(event) => setCreatorCode(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label></section>
      <button disabled={busy || !lines.length} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Recording…" : "Record order"}</button>
      </fieldset>
    </form>
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}
