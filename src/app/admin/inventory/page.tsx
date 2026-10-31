"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

interface Location { id: string; key: string; name: string }
interface Variant { id: string; product_title: string; sku: string; color_name: string }
interface Balance extends Variant {
  variant_id: string; location_id: string; location_name: string; location_key: string;
  on_hand: number; reserved: number; available: number;
  low_stock_threshold: number | null;
}
interface ZeroBalancePage { items: Balance[]; total_count: number; limit: number; offset: number }
interface Movement {
  id: string; delta_on_hand: number; delta_reserved: number; reason: string;
  actor_id: string | null; notes: string | null; created_at: string;
}

const movementLabel = (movement: Movement) => {
  const delta = movement.delta_on_hand > 0 ? `+${movement.delta_on_hand}` : movement.delta_on_hand;
  return `${movement.reason.replaceAll("_", " ")} · ${delta} on hand`;
};

export default function InventoryAdminPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [zeroOnly, setZeroOnly] = useState(() =>
    typeof window !== "undefined"
      && new URLSearchParams(window.location.search).get("availability") === "zero"
  );
  const [lowOnly, setLowOnly] = useState(() =>
    typeof window !== "undefined"
      && new URLSearchParams(window.location.search).get("availability") === "low"
  );
  const [filteredTotal, setFilteredTotal] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selected, setSelected] = useState<Balance | null>(null);
  const [movements, setMovements] = useState<Movement[]>([]);
  const selectionRequest = useRef(0);
  const inventoryRequest = useRef(0);
  const [query, setQuery] = useState("");
  const [receiveVariant, setReceiveVariant] = useState("");
  const [receiveLocation, setReceiveLocation] = useState("");
  const [receiveQuantity, setReceiveQuantity] = useState("");
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustNote, setAdjustNote] = useState("");
  const [thresholdValue, setThresholdValue] = useState("");
  const [receiveRetry, setReceiveRetry] = useState<{ fingerprint: string; key: string } | null>(null);
  const [adjustRetry, setAdjustRetry] = useState<{ fingerprint: string; key: string } | null>(null);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<StaffIdentity>("auth/me").then((user) => {
        if (active) setIdentity(user);
      }).catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      }).finally(() => {
        if (active) setLoading(false);
      });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function loadInventory() {
    const inventoryRequestId = ++inventoryRequest.current;
    const selectionRequestId = selectionRequest.current;
    const selectedAtStart = selected;
    setBusy(true); setError(null);
    try {
      const [locationRows, variantRows, balanceResponse] = await Promise.all([
        staffJson<Location[]>("admin/inventory/locations"),
        staffJson<Variant[]>("admin/inventory/variants"),
        zeroOnly || lowOnly
          ? staffJson<ZeroBalancePage>(`${lowOnly ? "admin/inventory/low-stock" : "admin/inventory/out-of-stock"}?limit=100&offset=0`)
          : staffJson<Balance[]>("admin/inventory/balances?limit=500"),
      ]);
      const balanceRows = zeroOnly || lowOnly
        ? (balanceResponse as ZeroBalancePage).items
        : (balanceResponse as Balance[]);
      if (inventoryRequestId !== inventoryRequest.current) return;
      setLocations(locationRows); setVariants(variantRows); setBalances(balanceRows);
      setFilteredTotal(zeroOnly || lowOnly ? (balanceResponse as ZeroBalancePage).total_count : null);
      setReceiveLocation((current) => current || locationRows[0]?.key || "");
      setReceiveVariant((current) => current || variantRows[0]?.id || "");
      if (selectedAtStart && selectionRequestId === selectionRequest.current) {
        const refreshed = balanceRows.find((row) => row.variant_id === selectedAtStart.variant_id && row.location_id === selectedAtStart.location_id);
        setSelected(refreshed ?? null);
        if (refreshed) setThresholdValue(refreshed.low_stock_threshold?.toString() ?? "");
        if (refreshed && identity?.permission_keys.includes("inventory.inspect")) {
          const history = await staffJson<{ items: Movement[] }>(`admin/inventory/movements?variant_id=${refreshed.variant_id}&location_id=${refreshed.location_id}&limit=50`);
          if (selectionRequestId === selectionRequest.current) setMovements(history.items);
        } else if (!refreshed) {
          setMovements([]);
        }
      }
    } catch (cause) {
      if (inventoryRequestId === inventoryRequest.current) {
        setError(cause instanceof Error ? cause.message : "Inventory could not be loaded.");
      }
    } finally {
      if (inventoryRequestId === inventoryRequest.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!identity?.permission_keys.includes("inventory.read")) return;
    const timer = window.setTimeout(() => void loadInventory(), 0);
    return () => window.clearTimeout(timer);
    // Initial load runs after the inventory permission is known.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity, zeroOnly, lowOnly]);

  async function loadMoreFilteredBalances() {
    if (loadingMore || balances.length >= (filteredTotal ?? 0)) return;
    const requestId = inventoryRequest.current;
    const queue = lowOnly ? "low-stock" : "out-of-stock";
    setLoadingMore(true); setError(null);
    try {
      const page = await staffJson<ZeroBalancePage>(
        `admin/inventory/${queue}?limit=100&offset=${balances.length}`
      );
      if (requestId === inventoryRequest.current) {
        setBalances((current) => [...current, ...page.items]);
        setFilteredTotal(page.total_count);
      }
    } catch (cause) {
      if (requestId === inventoryRequest.current) {
        setError(cause instanceof Error ? cause.message : "More inventory could not be loaded.");
      }
    } finally {
      if (requestId === inventoryRequest.current) setLoadingMore(false);
    }
  }

  const visibleBalances = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return balances;
    return balances.filter((row) => `${row.product_title} ${row.sku} ${row.color_name} ${row.location_name}`.toLowerCase().includes(normalized));
  }, [balances, query]);

  async function openBalance(balance: Balance) {
    const requestId = ++selectionRequest.current;
    setSelected(balance); setError(null); setNotice(null); setMovements([]);
    setThresholdValue(balance.low_stock_threshold?.toString() ?? "");
    if (!identity?.permission_keys.includes("inventory.inspect")) return;
    try {
      const history = await staffJson<{ items: Movement[] }>(`admin/inventory/movements?variant_id=${balance.variant_id}&location_id=${balance.location_id}&limit=50`);
      if (requestId === selectionRequest.current) setMovements(history.items);
    } catch (cause) {
      if (requestId === selectionRequest.current) {
        setError(cause instanceof Error ? cause.message : "Movement history could not be loaded.");
      }
    }
  }

  function clearSelection() {
    selectionRequest.current += 1;
    setSelected(null);
    setMovements([]);
  }

  function changeAvailability(queue: "all" | "zero" | "low") {
    inventoryRequest.current += 1;
    setLoadingMore(false);
    clearSelection();
    setZeroOnly(queue === "zero");
    setLowOnly(queue === "low");
    window.history.replaceState(null, "", queue === "all"
      ? "/admin/inventory"
      : `/admin/inventory?availability=${queue}`);
  }

  async function saveThreshold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(null); setNotice(null);
    const threshold = thresholdValue.trim() === "" ? null : Number(thresholdValue);
    try {
      const updated = await staffJson<Balance>("admin/inventory/thresholds", {
        ...jsonBody({
          variant_id: selected.variant_id,
          location_id: selected.location_id,
          threshold,
        }),
        method: "PATCH",
      });
      setSelected({ ...selected, low_stock_threshold: updated.low_stock_threshold });
      setNotice(threshold === null ? "Low-stock alert cleared." : `Alert set at ${threshold} available units.`);
      await loadInventory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Low-stock threshold could not be saved.");
    } finally { setBusy(false); }
  }

  async function receive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    const fingerprint = `${receiveVariant}:${receiveLocation}:${receiveQuantity}`;
    const idempotencyKey = receiveRetry?.fingerprint === fingerprint ? receiveRetry.key : crypto.randomUUID();
    setReceiveRetry({ fingerprint, key: idempotencyKey });
    try {
      await staffJson("admin/inventory/receive", jsonBody({
        variant_id: receiveVariant, location_key: receiveLocation,
        quantity: Number(receiveQuantity), idempotency_key: idempotencyKey,
      }));
      setReceiveQuantity(""); setReceiveRetry(null); setNotice("Stock received and recorded in the movement ledger.");
      await loadInventory();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Stock could not be received."); }
    finally { setBusy(false); }
  }

  async function adjust(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(null); setNotice(null);
    const fingerprint = `${selected.variant_id}:${selected.location_id}:${adjustDelta}:${adjustNote.trim()}`;
    const idempotencyKey = adjustRetry?.fingerprint === fingerprint ? adjustRetry.key : crypto.randomUUID();
    setAdjustRetry({ fingerprint, key: idempotencyKey });
    try {
      await staffJson("admin/inventory/adjust", jsonBody({
        variant_id: selected.variant_id, location_id: selected.location_id,
        delta: Number(adjustDelta), reason: "ADJUST", notes: adjustNote.trim(),
        idempotency_key: idempotencyKey,
      }));
      setAdjustDelta(""); setAdjustNote(""); setAdjustRetry(null); setNotice("Adjustment saved with its reason in the movement ledger.");
      await loadInventory();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Adjustment could not be saved."); }
    finally { setBusy(false); }
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("inventory.read")) return <p role="alert">Inventory access is not included in your permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="space-y-8">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Inventory</h1><p className="mt-2 text-sm text-charcoal/75">Review on-hand, reserved, and available units by SKU and location.</p></div>
      <Link href="/admin" className="text-sm text-terracotta underline">Back to staff home</Link>
    </header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    {(identity.permission_keys.includes("inventory.receive") || identity.permission_keys.includes("inventory.adjust")) && <div className="grid gap-5 lg:grid-cols-2">
      {identity.permission_keys.includes("inventory.receive") && <section className="rounded-2xl border border-sand bg-white p-5"><h2 className="heading-sm">Receive stock</h2><p className="mt-1 text-sm text-charcoal/75">Adds units to on-hand and records a receive movement.</p><form onSubmit={(event) => void receive(event)} className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="text-sm sm:col-span-3">SKU<select required value={receiveVariant} onChange={(event) => setReceiveVariant(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2">{variants.map((variant) => <option key={variant.id} value={variant.id}>{variant.sku} · {variant.product_title} · {variant.color_name}</option>)}</select></label>
        <label className="text-sm sm:col-span-2">Location<select required value={receiveLocation} onChange={(event) => setReceiveLocation(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2">{locations.map((location) => <option key={location.id} value={location.key}>{location.name}</option>)}</select></label>
        <label className="text-sm">Quantity<input required min="1" step="1" type="number" value={receiveQuantity} onChange={(event) => setReceiveQuantity(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
        <button disabled={busy || !variants.length || !locations.length} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-3">Receive stock</button>
      </form></section>}
      {identity.permission_keys.includes("inventory.adjust") && <section className="rounded-2xl border border-sand bg-white p-5"><h2 className="heading-sm">Adjust selected balance</h2><p className="mt-1 text-sm text-charcoal/75">Enter a positive or negative count correction and document why.</p>{selected ? <><p className="mt-3 text-sm font-medium">{selected.sku} · {selected.product_title} · {selected.location_name}</p><p className="text-xs text-charcoal/75">{selected.on_hand} on hand · {selected.reserved} reserved · {selected.available} available</p><form onSubmit={(event) => void adjust(event)} className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Quantity change<input required step="1" type="number" value={adjustDelta} onChange={(event) => setAdjustDelta(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
        <label className="text-sm sm:row-span-2">Reason / notes<textarea required minLength={3} maxLength={500} value={adjustNote} onChange={(event) => setAdjustNote(event.target.value)} className="mt-1 block min-h-20 w-full rounded-lg border border-sand p-2" /></label>
        <button disabled={busy || !Number(adjustDelta)} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Save adjustment</button>
      </form></> : <p className="mt-4 text-sm text-charcoal/75">Select a balance below to record an adjustment.</p>}</section>}
    </div>}
    <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-medium">{lowOnly ? "Below configured stock threshold" : zeroOnly ? "Balances with no available units" : "Stock balances"}</h2><p className="mt-1 text-xs text-charcoal/75">{(zeroOnly || lowOnly) ? `Showing ${balances.length} of ${filteredTotal ?? 0}. ` : ""}Select a row to inspect its recent movement history.{(zeroOnly || lowOnly) && balances.length < (filteredTotal ?? 0) ? " Search applies to loaded rows; load more to expand the results." : ""}</p></div><div className="flex flex-wrap items-center gap-2">{(zeroOnly || lowOnly) && <button type="button" onClick={() => changeAvailability("all")} className="rounded-lg border border-sand px-3 py-2 text-sm">Show all balances</button>}{!zeroOnly && <button type="button" onClick={() => changeAvailability("zero")} className="rounded-lg border border-sand px-3 py-2 text-sm">No available units</button>}{!lowOnly && <button type="button" onClick={() => changeAvailability("low")} className="rounded-lg border border-sand px-3 py-2 text-sm">Below threshold</button>}<input aria-label="Search inventory" placeholder="Search SKU, product, location" value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-64 rounded-lg border border-sand p-2 text-sm" /></div></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[48rem] text-left text-sm"><thead><tr className="border-b border-sand text-xs uppercase tracking-wide text-charcoal/75"><th className="py-3 pr-3">SKU / product</th><th className="py-3 pr-3">Location</th><th className="py-3 pr-3">On hand</th><th className="py-3 pr-3">Reserved</th><th className="py-3 pr-3">Available</th><th className="py-3">Alert at</th></tr></thead><tbody>{visibleBalances.map((balance) => <tr key={`${balance.variant_id}:${balance.location_id}`}><td className="border-b border-sand/60 py-3 pr-3"><button type="button" onClick={() => void openBalance(balance)} className="text-left hover:text-terracotta"><strong>{balance.sku}</strong><span className="block text-xs text-charcoal/75">{balance.product_title} · {balance.color_name}</span></button></td><td className="border-b border-sand/60 py-3 pr-3">{balance.location_name}</td><td className="border-b border-sand/60 py-3 pr-3">{balance.on_hand}</td><td className="border-b border-sand/60 py-3 pr-3">{balance.reserved}</td><td className="border-b border-sand/60 py-3 pr-3">{balance.available}</td><td className="border-b border-sand/60 py-3">{balance.low_stock_threshold ?? "Not set"}</td></tr>)}</tbody></table></div>
      {!visibleBalances.length && <p className="text-sm text-charcoal/75">{busy ? "Loading inventory…" : "No stock balances match this search."}</p>}
      {(zeroOnly || lowOnly) && balances.length < (filteredTotal ?? 0) && <button type="button" onClick={() => void loadMoreFilteredBalances()} disabled={loadingMore} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-50">{loadingMore ? "Loading…" : lowOnly ? "Load more low-stock balances" : "Load more unavailable balances"}</button>}
    </section>
    {selected && identity.permission_keys.includes("inventory.thresholds.manage") && <section className="rounded-2xl border border-sand bg-white p-5"><h2 className="font-medium">Low-stock alert · {selected.sku}</h2><p className="mt-1 text-sm text-charcoal/75">Set the available-unit level that should appear in the low-stock queue. Leave blank to disable this alert.</p><form onSubmit={(event) => void saveThreshold(event)} className="mt-4 flex flex-wrap items-end gap-3"><label className="text-sm">Alert at or below<input type="number" min="0" step="1" value={thresholdValue} onChange={(event) => setThresholdValue(event.target.value)} placeholder="No threshold" className="mt-1 block w-48 rounded-lg border border-sand p-2" /></label><button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Save alert level</button></form></section>}
    {selected && identity.permission_keys.includes("inventory.inspect") && <section className="space-y-4 rounded-2xl border border-sand bg-white p-5"><h2 className="font-medium">Recent movements · {selected.sku}</h2>{movements.length ? <ol className="space-y-3">{movements.map((movement) => <li key={movement.id} className="flex flex-wrap justify-between gap-2 border-b border-sand/60 pb-3 text-sm"><span>{movementLabel(movement)}{movement.notes && <span className="block text-xs text-charcoal/75">{movement.notes}</span>}<span className="mt-1 block text-xs text-charcoal/75">{movement.actor_id ? `Staff ${movement.actor_id.slice(0, 8)}` : "System"}</span></span><time className="text-xs text-charcoal/75">{new Date(movement.created_at).toLocaleString()}</time></li>)}</ol> : <p className="text-sm text-charcoal/75">{busy ? "Loading movement history…" : "No movements recorded for this balance."}</p>}</section>}
  </div>;
}
