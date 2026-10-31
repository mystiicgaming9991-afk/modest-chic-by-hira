"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";

interface PendingCodOrder {
  id: string;
  number: string;
  state: string;
  customer_name: string | null;
  customer_phone: string | null;
  total_minor: number;
  fulfillment_method: string;
  address_city: string | null;
  stock_reservation_exception: boolean;
}

interface PendingCodPage {
  items: PendingCodOrder[];
  total_count: number;
  limit: number;
  offset: number;
}

export default function CodQueuePage() {
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [orders, setOrders] = useState<PendingCodOrder[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const loadedCount = useRef(0);
  const queueRequest = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [contactRetry, setContactRetry] = useState<{ fingerprint: string; key: string } | null>(null);

  const load = useCallback(async (append = false) => {
    const requestId = ++queueRequest.current;
    if (append) setLoadingMore(true);
    else {
      setLoading(true);
      setLoadingMore(false);
    }
    try {
      const user = await staffJson<StaffIdentity>("auth/me");
      if (requestId !== queueRequest.current) return;
      if (!user.permission_keys.includes("order.read")) throw new Error("Order access is required.");
      setIdentity(user);
      const offset = append ? loadedCount.current : 0;
      const page = await staffJson<PendingCodPage>(`admin/orders/cod/pending?limit=100&offset=${offset}`);
      if (requestId !== queueRequest.current) return;
      setOrders((current) => append ? [...current, ...page.items] : page.items);
      loadedCount.current = offset + page.items.length;
      setTotalCount(page.total_count);
      setError(null);
    } catch (cause) {
      if (requestId === queueRequest.current) {
        if (!append) { setOrders([]); setTotalCount(0); loadedCount.current = 0; }
        setError(cause instanceof Error ? cause.message : "Queue could not be loaded.");
      }
    } finally {
      if (requestId === queueRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function submit(orderId: string, action: string, channel: string, notes: string, outcome?: string) {
    setBusy(true); setError(null);
    try {
      const contactOutcome = outcome ?? "NO_ANSWER";
      const fingerprint = `${orderId}:${channel}:${contactOutcome}:${notes.trim()}`;
      const idempotencyKey = contactRetry?.fingerprint === fingerprint ? contactRetry.key : crypto.randomUUID();
      if (action === "contact-attempts") setContactRetry({ fingerprint, key: idempotencyKey });
      const body = action === "contact-attempts"
        ? { channel, outcome: contactOutcome, notes, idempotency_key: idempotencyKey }
        : { channel, notes };
      await staffJson(`admin/orders/cod/${orderId}/${action}`, jsonBody(body));
      if (action === "contact-attempts") setContactRetry(null);
      await load();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Decision could not be recorded.";
      await load();
      setError(message);
    } finally { setBusy(false); }
  }

  return <div className="space-y-6">
    <div><Link href="/admin" className="text-sm text-terracotta hover:underline">← Staff home</Link><h1 className="heading-md mt-3">Pending COD confirmation</h1><p className="mt-1 text-sm text-charcoal/75">Record contact before dispatch. A decision checks the current order and reservation.</p></div>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error} {!identity && <Link href="/admin/login" className="underline">Sign in</Link>}</p>}
    {loading ? <p role="status">Loading queue…</p> : orders.length === 0 ? <p className="rounded-xl border border-sand bg-white p-6">No pending COD orders.</p> : <><p className="text-sm text-charcoal/75">Showing {orders.length} of {totalCount} pending COD orders.</p><div className="space-y-4">{orders.map((order) => <OrderCard key={order.id} order={order} busy={busy} canConfirm={identity?.permission_keys.includes("order.confirm") ?? false} onSubmit={submit} />)}</div>{orders.length < totalCount && <button type="button" onClick={() => void load(true)} disabled={loading || loadingMore || busy} className="rounded-full border border-charcoal px-5 py-2 text-sm disabled:opacity-50">{loadingMore ? "Loading…" : "Load more orders"}</button>}</>}
  </div>;
}

function OrderCard({ order, busy, canConfirm, onSubmit }: {
  order: PendingCodOrder;
  busy: boolean;
  canConfirm: boolean;
  onSubmit: (orderId: string, action: string, channel: string, notes: string, outcome?: string) => Promise<void>;
}) {
  const [channel, setChannel] = useState("PHONE");
  const [notes, setNotes] = useState("");
  return <article className="rounded-2xl border border-sand bg-white p-6">
    <div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-medium">{order.number}</h2><p className="text-sm text-charcoal/75">{order.customer_name} · {order.customer_phone}</p><p className="text-sm text-charcoal/75">{order.fulfillment_method.toLowerCase()} · {order.address_city}</p></div><p className="font-medium">Rs. {(order.total_minor / 100).toLocaleString("en-PK")}</p></div>
    {canConfirm && <div className="mt-5 space-y-3 border-t border-sand pt-4">
      <div className="flex flex-wrap gap-3"><label className="text-sm font-medium">Channel<select value={channel} onChange={(event) => setChannel(event.target.value)} className="ml-2 rounded-lg border border-sand bg-white p-2"><option value="PHONE">Phone</option><option value="SMS">SMS</option><option value="WHATSAPP">WhatsApp</option></select></label></div>
      <label className="block text-sm font-medium">Contact notes<textarea required maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      {order.stock_reservation_exception && <p role="alert" className="rounded-lg bg-rust/10 p-3 text-sm text-rust">Live stock reservations do not cover this order. Confirmation is blocked until the stock exception is resolved.</p>}
      <div className="flex flex-wrap gap-2">
        <button disabled={busy || !notes.trim()} onClick={() => void onSubmit(order.id, "contact-attempts", channel, notes)} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-40">No answer</button>
        <button disabled={busy || !notes.trim()} onClick={() => void onSubmit(order.id, "contact-attempts", channel, notes, "FOLLOW_UP")} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-40">Follow up</button>
        <button disabled={busy || !notes.trim() || order.stock_reservation_exception} onClick={() => void onSubmit(order.id, "confirm", channel, notes)} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-40">Confirm order</button>
        <button disabled={busy || !notes.trim()} onClick={() => void onSubmit(order.id, "decline", channel, notes)} className="rounded-lg border border-rust/40 px-4 py-2 text-sm text-rust disabled:opacity-40">Decline order</button>
      </div>
    </div>}
  </article>;
}
