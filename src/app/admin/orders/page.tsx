"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type OrderState = "PENDING_CONFIRMATION" | "CONFIRMED" | "PROCESSING" | "FULFILLED" | "COMPLETED" | "CANCELLED";
type OrderSource = "STOREFRONT" | "MANUAL" | "SOCIAL";
interface OrderSummary { id: string; number: string; source: OrderSource; state: OrderState; payment_state: string; payment_method: string; fulfillment_method: string; customer_name: string | null; customer_phone: string | null; total_minor: number; currency: string; created_at: string | null }
interface OrderDetail extends OrderSummary {
  stock_reservation_exception: boolean;
  customer_id: string | null;
  customer_email: string | null;
  address: { line1: string | null; line2: string | null; area: string | null; city: string | null; postal_code: string | null; country_code: string | null; delivery_notes: string | null };
  subtotal_minor: number; discount_minor: number; shipping_charge_minor: number;
  policy_version_id: string | null;
  accepted_policies?: Array<{ type: string; policy_version_id: string; version: number }>;
  attribution: { source: string | null; campaign: string | null; creator_code: string | null };
  items: Array<{ id: string; sku: string; product_title: string; variant_name: string; quantity: number; fulfilled_quantity: number; unit_price_minor: number; sale_price_minor: number | null; discount_allocated_minor: number; line_total_minor: number }>;
  events: Array<{ event_type: string; previous_state: string | null; new_state: string | null; actor_type: string; actor_id: string | null; metadata: Record<string, unknown> | null; effective_at: string | null }>;
  payments: Array<{ id: string; provider: string; method: string; attempt_number: number; amount_minor: number; currency: string; status: string; provider_txn_id: string | null; events: Array<{ event_type: string; created_at: string | null }> }>;
  shipments: Array<{ id: string; merchant_reference: string | null; courier: string | null; tracking_number: string | null; status: string; shipped_at: string | null; delivered_at: string | null; items: Array<{ order_item_id: string; quantity: number }>; events: Array<{ event_type: string; location: string | null; notes: string | null; actor_id: string | null; created_at: string | null }> }>;
  pickups: Array<{ id: string; status: string; ready_at: string | null; collected_at: string | null }>;
  returns: Array<{ id: string; state: string; reason: string | null }>;
  refunds: Array<{ id: string; amount_minor: number; state: string; reason: string | null; provider_reference: string | null }>;
}

const STATES: OrderState[] = ["PENDING_CONFIRMATION", "CONFIRMED", "PROCESSING", "FULFILLED", "COMPLETED", "CANCELLED"];
const money = (minor: number) => `PKR ${(minor / 100).toFixed(2)}`;

function isReadyForHandoff(order: OrderDetail): boolean {
  if (!order.shipments.length || !order.items.length || order.shipments.some((shipment) => shipment.status !== "PACKED")) return false;
  return order.items.every((item) => {
    const packed = order.shipments.reduce((total, shipment) => total + shipment.items
      .filter((allocation) => allocation.order_item_id === item.id)
      .reduce((sum, allocation) => sum + allocation.quantity, 0), 0);
    return packed === item.quantity - item.fulfilled_quantity;
  });
}

function canCancelOrder(order: OrderDetail): boolean {
  return ["PENDING", "FAILED"].includes(order.payment_state)
    && ["PENDING_CONFIRMATION", "CONFIRMED", "PROCESSING"].includes(order.state)
    && order.items.length > 0
    && order.items.every((item) => item.fulfilled_quantity === 0)
    && order.shipments.every((shipment) => shipment.status === "PACKED")
    && order.pickups.every((pickup) => pickup.status.toUpperCase() !== "COLLECTED");
}

export default function OrdersPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [query, setQuery] = useState("");
  const [state, setState] = useState(() =>
    typeof window !== "undefined"
      && new URLSearchParams(window.location.search).get("work") === "packing"
      ? "PROCESSING"
      : ""
  );
  const [packingQueue, setPackingQueue] = useState(() =>
    typeof window !== "undefined"
      && new URLSearchParams(window.location.search).get("work") === "packing"
  );
  const [stockExceptionQueue, setStockExceptionQueue] = useState(() =>
    typeof window !== "undefined"
      && new URLSearchParams(window.location.search).get("work") === "stock-exceptions"
  );
  const [source, setSource] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shipmentNotice, setShipmentNotice] = useState<string | null>(null);
  const [packQuantities, setPackQuantities] = useState<Record<string, string>>({});
  const [processingRetry, setProcessingRetry] = useState<{ orderId: string; key: string } | null>(null);
  const [packRetry, setPackRetry] = useState<{ fingerprint: string; key: string } | null>(null);
  const [handoffRetry, setHandoffRetry] = useState<{ orderId: string; key: string } | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelRetry, setCancelRetry] = useState<{ fingerprint: string; key: string } | null>(null);
  const orderListRequest = useRef(0);
  const orderDetailRequest = useRef(0);

  function clearPackingQueueParameter() {
    const params = new URLSearchParams(window.location.search);
    params.delete("work");
    const queryString = params.toString();
    window.history.replaceState(null, "", `/admin/orders${queryString ? `?${queryString}` : ""}`);
  }

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => staffJson<StaffIdentity>("auth/me").then((user) => {
      if (active) setIdentity(user);
    }).catch((cause) => {
      if (!active) return;
      if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
      else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
    }).finally(() => { if (active) setLoading(false); }), 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function search(
    event?: FormEvent<HTMLFormElement>,
    nextOffset = 0,
    stateFilter = state,
    packingFilter = packingQueue,
    stockExceptionFilter = stockExceptionQueue,
  ) {
    const requestId = ++orderListRequest.current;
    orderDetailRequest.current += 1;
    event?.preventDefault(); setBusy(true); setError(null); setOffset(nextOffset);
    setSelected(null);
    const params = new URLSearchParams({ limit: "50", offset: String(nextOffset) });
    if (query.trim()) params.set("q", query.trim());
    if (stateFilter || packingFilter) params.set("state", stateFilter || "PROCESSING");
    if (packingFilter) params.set("packing_only", "true");
    if (stockExceptionFilter) params.set("stock_exception_only", "true");
    if (source) params.set("source", source);
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    try {
      const result = await staffJson<OrderSummary[]>(`admin/orders?${params.toString()}`);
      if (requestId === orderListRequest.current) {
        orderDetailRequest.current += 1;
        setOrders(result);
        setSelected(null);
      }
    } catch (cause) {
      if (requestId === orderListRequest.current) {
        setError(cause instanceof Error ? cause.message : "Orders could not be loaded.");
      }
    } finally {
      if (requestId === orderListRequest.current) setBusy(false);
    }
  }

  async function openOrder(order: OrderSummary) {
    const requestId = ++orderDetailRequest.current;
    setBusy(true); setError(null); setShipmentNotice(null); setPackQuantities({});
    setPackRetry(null);
    setCancelReason("");
    setCancelRetry(null);
    setSelected(null);
    try {
      const detail = await staffJson<OrderDetail>(`admin/orders/${order.id}`);
      if (requestId === orderDetailRequest.current) setSelected(detail);
    } catch (cause) {
      if (requestId === orderDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Order details could not be loaded.");
      }
    } finally {
      if (requestId === orderDetailRequest.current) setBusy(false);
    }
  }

  async function startProcessing(order: OrderDetail) {
    const requestId = orderDetailRequest.current;
    setBusy(true); setError(null);
    const idempotencyKey = processingRetry?.orderId === order.id ? processingRetry.key : crypto.randomUUID();
    setProcessingRetry({ orderId: order.id, key: idempotencyKey });
    try {
      const updated = await staffJson<OrderSummary>(`admin/orders/${order.id}/start-processing`, jsonBody({ idempotency_key: idempotencyKey }));
      if (requestId === orderDetailRequest.current) setSelected((current) => current?.id === order.id ? { ...current, ...updated } : current);
      setOrders((current) => current.map((entry) => entry.id === updated.id ? { ...entry, ...updated } : entry));
      setProcessingRetry(null);
    } catch (cause) {
      if (requestId === orderDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Order could not enter processing.");
      }
    } finally {
      if (requestId === orderDetailRequest.current) setBusy(false);
    }
  }

  async function packShipment(order: OrderDetail) {
    const requestId = orderDetailRequest.current;
    const allocations = order.items.flatMap((item) => {
      const quantity = Number(packQuantities[item.id] || 0);
      return quantity > 0 ? [{ order_item_id: item.id, quantity }] : [];
    });
    if (!allocations.length) return;
    setBusy(true); setError(null); setShipmentNotice(null);
    const fingerprint = JSON.stringify(allocations);
    const idempotencyKey = packRetry?.fingerprint === fingerprint ? packRetry.key : crypto.randomUUID();
    setPackRetry({ fingerprint, key: idempotencyKey });
    try {
      const shipment = await staffJson<{ merchant_reference: string; status: string }>(
        `admin/orders/${order.id}/shipments/pack`,
        jsonBody({ idempotency_key: idempotencyKey, allocations }),
      );
      const updated = await staffJson<OrderDetail>(`admin/orders/${order.id}`);
      if (requestId === orderDetailRequest.current) {
        setSelected((current) => current?.id === order.id ? updated : current);
        setPackQuantities({}); setPackRetry(null);
        setShipmentNotice(`Packed shipment ${shipment.merchant_reference}. Courier booking was not requested.`);
      }
    } catch (cause) {
      if (requestId === orderDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Shipment could not be packed.");
      }
    } finally {
      if (requestId === orderDetailRequest.current) setBusy(false);
    }
  }

  async function handoffDelivery(order: OrderDetail) {
    const requestId = orderDetailRequest.current;
    setBusy(true); setError(null); setShipmentNotice(null);
    const idempotencyKey = handoffRetry?.orderId === order.id ? handoffRetry.key : crypto.randomUUID();
    setHandoffRetry({ orderId: order.id, key: idempotencyKey });
    try {
      const updated = await staffJson<OrderSummary>(`admin/orders/${order.id}/handoff`, jsonBody({ idempotency_key: idempotencyKey }));
      const detail = await staffJson<OrderDetail>(`admin/orders/${order.id}`);
      if (requestId === orderDetailRequest.current) setSelected((current) => current?.id === order.id ? detail : current);
      setOrders((current) => current.map((entry) => entry.id === updated.id ? { ...entry, ...updated } : entry));
      setHandoffRetry(null);
      if (requestId === orderDetailRequest.current) {
        setShipmentNotice("All parcels were handed off. Reserved stock was consumed and the order is fulfilled.");
      }
    } catch (cause) {
      if (requestId === orderDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Delivery handoff could not be recorded.");
      }
    } finally {
      if (requestId === orderDetailRequest.current) setBusy(false);
    }
  }

  async function cancelOrder(order: OrderDetail) {
    const requestId = orderDetailRequest.current;
    const reason = cancelReason.trim();
    if (!reason) return;
    setBusy(true); setError(null); setShipmentNotice(null);
    const fingerprint = `${order.id}:${reason}`;
    const idempotencyKey = cancelRetry?.fingerprint === fingerprint ? cancelRetry.key : crypto.randomUUID();
    setCancelRetry({ fingerprint, key: idempotencyKey });
    try {
      const updated = await staffJson<OrderSummary>(
        `admin/orders/${order.id}/cancel`,
        jsonBody({ idempotency_key: idempotencyKey, reason }),
      );
      const detail = await staffJson<OrderDetail>(`admin/orders/${order.id}`);
      if (requestId === orderDetailRequest.current) setSelected((current) => current?.id === order.id ? detail : current);
      setOrders((current) => current.map((entry) => entry.id === updated.id ? { ...entry, ...updated } : entry));
      setCancelRetry(null);
      if (requestId === orderDetailRequest.current) {
        setShipmentNotice("Order cancelled. Active stock and any eligible coupon reservation were released.");
      }
    } catch (cause) {
      if (requestId === orderDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Order could not be cancelled.");
      }
    } finally {
      if (requestId === orderDetailRequest.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!identity?.permission_keys.includes("order.read")) return;
    const requestedParams = new URLSearchParams(window.location.search);
    const requestedState = requestedParams.get("state");
    const initialPackingQueue = requestedParams.get("work") === "packing";
    const initialStockExceptionQueue = requestedParams.get("work") === "stock-exceptions";
    const initialState = initialPackingQueue
      ? "PROCESSING"
      : initialStockExceptionQueue
        ? ""
        : STATES.includes(requestedState as OrderState) ? requestedState! : "";
    const timer = window.setTimeout(() => {
      if (initialPackingQueue) setPackingQueue(true);
      if (initialStockExceptionQueue) setStockExceptionQueue(true);
      if (initialState) setState(initialState);
      void search(undefined, 0, initialState, initialPackingQueue, initialStockExceptionQueue);
    }, 0);
    return () => window.clearTimeout(timer);
    // Initial load is intentionally bound to the authenticated identity only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity]);

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("order.read")) return <p role="alert">Order access is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;
  const canReadPaymentDetails = identity.permission_keys.includes("payment.read");
  const canReadRefundDetails = canReadPaymentDetails
    || identity.permission_keys.includes("refund.request")
    || identity.permission_keys.includes("refund.approve");
  const canReadCustomerDetails = identity.permission_keys.includes("customer.read");

  return <div className="space-y-8">
    <header><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Order history</h1><p className="mt-2 text-sm text-charcoal/75">Search by order number or customer context. Accepted item snapshots remain available even if catalog listings change.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {shipmentNotice && <p role="status" className="rounded-lg bg-warm-cream p-4">{shipmentNotice}</p>}
    {(packingQueue || stockExceptionQueue) && <p role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-warm-cream p-4 text-sm">{packingQueue ? "Showing delivery orders with units still eligible to pack." : "Showing COD orders awaiting confirmation or fulfillment orders with outstanding units that lack active stock reservations."}<button type="button" onClick={() => { setPackingQueue(false); setStockExceptionQueue(false); setState(""); clearPackingQueueParameter(); void search(undefined, 0, "", false, false); }} className="text-terracotta underline">Show all orders</button></p>}
    <form onSubmit={(event) => void search(event)} className="grid gap-3 rounded-2xl border border-sand bg-white p-5 sm:grid-cols-3">
      <label className="text-sm font-medium sm:col-span-3">Order number, customer, or phone<input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={100} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <label className="text-sm font-medium">State<select value={state} onChange={(event) => { setState(event.target.value); if (event.target.value !== "PROCESSING") { setPackingQueue(false); clearPackingQueueParameter(); } if (stockExceptionQueue) { setStockExceptionQueue(false); clearPackingQueueParameter(); } }} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">All states</option>{STATES.map((entry) => <option key={entry} value={entry}>{entry.replaceAll("_", " ")}</option>)}</select></label>
      <label className="text-sm font-medium">Source<select value={source} onChange={(event) => setSource(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">All sources</option>{(["STOREFRONT", "MANUAL", "SOCIAL"] as const).map((entry) => <option key={entry}>{entry}</option>)}</select></label>
      <div className="grid grid-cols-2 gap-2"><label className="text-sm font-medium">From<input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label><label className="text-sm font-medium">Through<input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label></div>
      <button disabled={busy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50 sm:col-span-3">Search orders</button>
    </form>
    <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.9fr)_minmax(30rem,1.4fr)]">
      <section className="space-y-3"><h2 className="font-medium">Results ({orders.length})</h2>{orders.length ? orders.map((order) => <button type="button" key={order.id} onClick={() => void openOrder(order)} className={`w-full rounded-xl border bg-white p-4 text-left ${selected?.id === order.id ? "border-terracotta" : "border-sand hover:border-terracotta/60"}`}>
        <span className="flex justify-between gap-3"><strong>{order.number}</strong><span className="text-sm">{money(order.total_minor)}</span></span><span className="mt-1 block text-sm text-charcoal/75">{order.customer_name || "Customer"} · {order.customer_phone || "No phone"}</span><span className="mt-1 block text-xs text-charcoal/75">{order.state.replaceAll("_", " ")} · {order.source} · {order.payment_method} {order.payment_state}</span>
      </button>) : <p className="rounded-xl border border-sand bg-white p-5 text-sm text-charcoal/75">{busy ? "Loading orders…" : "No matching orders."}</p>}
      <div className="flex justify-between"><button disabled={busy || offset === 0} onClick={() => void search(undefined, Math.max(0, offset - 50))} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-40">Previous</button><button disabled={busy || orders.length < 50} onClick={() => void search(undefined, offset + 50)} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-40">Next</button></div></section>
      <section className="min-h-96 rounded-2xl border border-sand bg-white p-5">{!selected ? <p className="text-sm text-charcoal/75">Select an order to inspect its accepted details and event history.</p> : <div className="space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-widest text-terracotta">{selected.source}</p><h2 className="heading-sm mt-1">{selected.number}</h2><p className="mt-1 text-sm text-charcoal/75">{selected.state.replaceAll("_", " ")} · {selected.fulfillment_method} · {selected.created_at ? new Date(selected.created_at).toLocaleString() : "Date unavailable"}</p></div><div className="flex gap-2">{selected.state === "PENDING_CONFIRMATION" && selected.payment_method === "COD" && <Link href="/admin/orders/cod" className="rounded-lg border border-sand px-3 py-2 text-sm">Open COD queue</Link>}{selected.state === "CONFIRMED" && identity.permission_keys.includes("fulfillment.pack") && <button type="button" disabled={busy || selected.stock_reservation_exception} onClick={() => void startProcessing(selected)} className="rounded-lg bg-charcoal px-3 py-2 text-sm text-white disabled:opacity-50">{busy ? "Saving…" : "Start processing"}</button>}</div></header>
        {selected.stock_reservation_exception && <p role="alert" className="rounded-lg bg-rust/10 p-3 text-sm text-rust">Live stock reservations do not cover this order. Processing and fulfillment actions are blocked until the stock exception is resolved.</p>}
        <div className="grid gap-4 sm:grid-cols-2"><div><h3 className="text-sm font-medium">Customer</h3><p className="mt-1 text-sm">{selected.customer_name || "—"}<br />{selected.customer_phone || "—"}{canReadCustomerDetails && selected.customer_email && <><br />{selected.customer_email}</>}</p></div><div><h3 className="text-sm font-medium">Address</h3><p className="mt-1 text-sm">{[selected.address.line1, selected.address.line2, selected.address.area, selected.address.city, selected.address.postal_code].filter(Boolean).join(", ") || "Pickup or no address"}{selected.address.delivery_notes && <><br />{selected.address.delivery_notes}</>}</p></div></div>
        <div><h3 className="text-sm font-medium">Accepted items</h3><ul className="mt-2 divide-y divide-sand">{selected.items.map((item) => <li key={item.id} className="flex justify-between gap-3 py-2 text-sm"><span>{item.product_title} · {item.variant_name} · {item.sku} × {item.quantity}{item.discount_allocated_minor > 0 && <small className="block text-charcoal/75">Discount {money(item.discount_allocated_minor)}</small>}</span><span>{money(item.line_total_minor)}</span></li>)}</ul></div>
        <div className="flex justify-end"><dl className="w-64 space-y-1 text-sm"><div className="flex justify-between"><dt>Subtotal</dt><dd>{money(selected.subtotal_minor)}</dd></div><div className="flex justify-between"><dt>Discount</dt><dd>−{money(selected.discount_minor)}</dd></div><div className="flex justify-between"><dt>Shipping</dt><dd>{money(selected.shipping_charge_minor)}</dd></div><div className="flex justify-between border-t border-sand pt-2 font-medium"><dt>Total</dt><dd>{money(selected.total_minor)}</dd></div></dl></div>
        {selected.accepted_policies?.length ? <section><h3 className="text-sm font-medium">Accepted policy versions</h3><ul className="mt-2 space-y-1 text-xs text-charcoal/75">{selected.accepted_policies.map((policy) => <li key={policy.type}>{policy.type.replaceAll("_", " ")} · version {policy.version} · {policy.policy_version_id}</li>)}</ul></section> : null}
        {selected.attribution.source || selected.attribution.campaign || selected.attribution.creator_code ? <div><h3 className="text-sm font-medium">Attribution</h3><p className="mt-1 text-sm text-charcoal/75">{[selected.attribution.source, selected.attribution.campaign, selected.attribution.creator_code].filter(Boolean).join(" · ")}</p></div> : null}
        {canReadPaymentDetails && <div><h3 className="text-sm font-medium">Payments</h3>{selected.payments.length ? <ul className="mt-2 space-y-2 text-sm">{selected.payments.map((payment) => <li key={payment.id} className="rounded-lg bg-cream p-3">{payment.method} · {payment.status} · {money(payment.amount_minor)}{payment.provider_txn_id && <span> · Ref {payment.provider_txn_id}</span>}<ul className="mt-1 text-xs text-charcoal/75">{payment.events.map((entry, index) => <li key={`${entry.event_type}:${index}`}>{entry.event_type} · {entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}</li>)}</ul></li>)}</ul> : <p className="mt-1 text-sm text-charcoal/75">No payment attempts recorded.</p>}</div>}
        {selected.shipments.length > 0 && <div><h3 className="text-sm font-medium">Shipments</h3><ul className="mt-2 space-y-2 text-sm">{selected.shipments.map((shipment) => <li key={shipment.id} className="rounded-lg bg-cream p-3"><strong>{shipment.status}</strong> · Ref {shipment.merchant_reference || "Pending"}{shipment.tracking_number && ` · ${shipment.tracking_number}`}<ul className="mt-1 text-xs text-charcoal/75">{shipment.items.map((allocation) => <li key={allocation.order_item_id}>{selected.items.find((item) => item.id === allocation.order_item_id)?.sku || "Order item"} × {allocation.quantity}</li>)}</ul></li>)}</ul></div>}
        {selected.fulfillment_method === "DELIVERY" && selected.state === "PROCESSING" && identity.permission_keys.includes("fulfillment.pack") && <form onSubmit={(event) => { event.preventDefault(); void packShipment(selected); }} className="space-y-3 rounded-xl border border-sand p-4"><div><h3 className="text-sm font-medium">Pack a shipment</h3><p className="mt-1 text-xs text-charcoal/75">This records parcel allocation only. Courier booking remains unavailable until a provider is approved.</p></div>{selected.items.map((item) => {
          const packed = selected.shipments.reduce((total, shipment) => total + shipment.items.filter((allocation) => allocation.order_item_id === item.id).reduce((sum, allocation) => sum + allocation.quantity, 0), 0);
          const remaining = Math.max(0, item.quantity - packed);
          return <label key={item.id} className="flex items-center justify-between gap-3 text-sm"><span>{item.sku} · {item.product_title} · {remaining} remaining</span><input aria-label={`Pack quantity for ${item.sku}`} type="number" min="0" max={remaining} step="1" value={packQuantities[item.id] ?? "0"} onChange={(event) => setPackQuantities((current) => ({ ...current, [item.id]: event.target.value }))} className="w-24 rounded-lg border border-sand p-2" /></label>;
        })}<button disabled={busy || !selected.items.some((item) => Number(packQuantities[item.id] || 0) > 0)} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Packing…" : "Record packed shipment"}</button></form>}
        {selected.fulfillment_method === "DELIVERY" && selected.state === "PROCESSING" && identity.permission_keys.includes("fulfillment.handoff") && <section className="space-y-2 rounded-xl border border-sand p-4"><h3 className="text-sm font-medium">Courier handoff</h3><p className="text-xs text-charcoal/75">Record the physical handoff after all remaining units have been packed. This consumes their reservations and fulfills the order.</p><button type="button" disabled={busy || !isReadyForHandoff(selected)} onClick={() => void handoffDelivery(selected)} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Recording handoff…" : "Record handoff and fulfill order"}</button>{!isReadyForHandoff(selected) && <p className="text-xs text-charcoal/75">Pack every remaining item before handoff is available.</p>}</section>}
        {identity.permission_keys.includes("order.cancel") && canCancelOrder(selected) && <section className="space-y-3 rounded-xl border border-rust/30 p-4"><div><h3 className="text-sm font-medium text-rust">Cancel order</h3><p className="mt-1 text-xs text-charcoal/75">Cancellation is available before courier handoff or pickup collection and only when no payment needs to be reversed.</p></div><label className="block text-sm font-medium">Reason<textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} maxLength={2000} rows={2} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label><button type="button" disabled={busy || !cancelReason.trim()} onClick={() => void cancelOrder(selected)} className="rounded-lg border border-rust/40 px-4 py-2 text-sm text-rust disabled:opacity-50">{busy ? "Cancelling…" : "Cancel order"}</button></section>}
        {selected.pickups.length > 0 && <div><h3 className="text-sm font-medium">Pickup</h3><p className="mt-1 text-sm">{selected.pickups.map((pickup) => `${pickup.status}${pickup.collected_at ? ` · collected ${new Date(pickup.collected_at).toLocaleString()}` : ""}`).join("; ")}</p></div>}
        {(selected.returns.length > 0 || (canReadRefundDetails && selected.refunds.length > 0)) && <div><h3 className="text-sm font-medium">Returns and refunds</h3><ul className="mt-2 space-y-1 text-sm">{selected.returns.map((entry) => <li key={entry.id}>Return · {entry.state} {entry.reason && `· ${entry.reason}`}</li>)}{canReadRefundDetails && selected.refunds.map((entry) => <li key={entry.id}>Refund · {entry.state} · {money(entry.amount_minor)} {entry.reason && `· ${entry.reason}`}</li>)}</ul></div>}
        <div><h3 className="text-sm font-medium">Order events</h3><ol className="mt-2 space-y-3 border-l border-sand pl-4">{selected.events.map((event, index) => <li key={`${event.event_type}:${index}`} className="text-sm"><p className="font-medium">{event.event_type.replaceAll(".", " ")}</p><p className="text-xs text-charcoal/75">{event.effective_at ? new Date(event.effective_at).toLocaleString() : ""} · {event.actor_type}</p>{event.metadata && Object.keys(event.metadata).length > 0 && <p className="mt-1 text-xs text-charcoal/75">{Object.entries(event.metadata).map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</p>}</li>)}</ol></div>
      </div>}</section>
    </div>
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}
