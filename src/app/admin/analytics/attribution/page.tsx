"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

interface AttributionRow {
  attribution_source: string | null;
  campaign: string | null;
  creator_code: string | null;
  order_source: string;
  order_count: number;
  subtotal_minor: number;
  discount_minor: number;
  shipping_charge_minor: number;
  accepted_total_minor: number;
  state_pending_confirmation: number;
  state_confirmed: number;
  state_processing: number;
  state_fulfilled: number;
  state_completed: number;
  state_cancelled: number;
}

interface AttributionReport {
  period: { from_date: string; to_date: string; time_zone: "UTC" };
  measurement: string;
  totals: {
    order_count: number;
    subtotal_minor: number;
    discount_minor: number;
    shipping_charge_minor: number;
    accepted_total_minor: number;
    current_order_states: Record<string, number>;
  };
  rows: AttributionRow[];
}

const money = (minor: number) => `PKR ${(minor / 100).toFixed(2)}`;
const utcDate = (date: Date) => date.toISOString().slice(0, 10);

export default function AttributionReportPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [report, setReport] = useState<AttributionReport | null>(null);
  const [filtersReady, setFiltersReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const today = new Date();
      const firstDay = new Date(today);
      firstDay.setUTCDate(firstDay.getUTCDate() - 29);
      setFromDate(utcDate(firstDay));
      setToDate(utcDate(today));
      setFiltersReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => staffJson<StaffIdentity>("auth/me")
      .then((user) => { if (active) setIdentity(user); })
      .catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      })
      .finally(() => { if (active) setLoading(false); }), 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function load(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
    try {
      setReport(await staffJson<AttributionReport>(`admin/analytics/attribution?${params.toString()}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Attribution report could not be loaded.");
      setReport(null);
    } finally { setBusy(false); }
  }

  useEffect(() => {
    if (!filtersReady || !identity?.permission_keys.includes("analytics.read")) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
    // Initial request follows identity; filters are submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity, filtersReady]);

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("analytics.read")) return <p role="alert">Analytics access is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="space-y-6">
    <header><Link href="/admin" className="text-sm text-terracotta underline">← Staff home</Link><p className="mt-4 text-xs uppercase tracking-widest text-terracotta">Marketing report</p><h1 className="heading-md mt-2">Creator attribution</h1><p className="mt-2 max-w-3xl text-sm text-charcoal/75">Orders are grouped by the attribution snapshot recorded when accepted. Price discounts are shown separately from creator attribution. These figures describe accepted order intake, not collected or settled revenue.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    <form onSubmit={(event) => void load(event)} className="grid gap-3 rounded-2xl border border-sand bg-white p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <label className="text-sm font-medium">From date (UTC)<input required type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <label className="text-sm font-medium">Through date (UTC)<input required type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <button disabled={busy || !fromDate || !toDate} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Loading…" : "Update report"}</button>
    </form>
    {report && <>
      <p className="text-xs text-charcoal/75">{report.measurement} Period: {report.period.from_date} to {report.period.to_date} UTC.</p>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["Attributed orders", String(report.totals.order_count)],
          ["Accepted order value", money(report.totals.accepted_total_minor)],
          ["Items before discount", money(report.totals.subtotal_minor)],
          ["Customer discounts", money(report.totals.discount_minor)],
          ["Shipping charged", money(report.totals.shipping_charge_minor)],
        ].map(([label, value]) => <div key={label} className="rounded-xl border border-sand bg-white p-4"><p className="text-xs uppercase tracking-wide text-charcoal/75">{label}</p><p className="mt-1 text-lg font-medium">{value}</p></div>)}
      </section>
      <div className="overflow-x-auto rounded-2xl border border-sand bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-sand bg-cream text-xs uppercase tracking-wide text-charcoal/75"><tr>{["Creator code", "Campaign", "Attribution source", "Order source", "Orders", "Accepted value", "Discount", "Current states"].map((label) => <th key={label} className="whitespace-nowrap px-4 py-3 font-medium">{label}</th>)}</tr></thead>
          <tbody className="divide-y divide-sand">{report.rows.map((row) => <tr key={[row.creator_code, row.campaign, row.attribution_source, row.order_source].join(":")}>
            <td className="whitespace-nowrap px-4 py-3">{row.creator_code || "—"}</td><td className="whitespace-nowrap px-4 py-3">{row.campaign || "—"}</td><td className="whitespace-nowrap px-4 py-3">{row.attribution_source || "—"}</td><td className="whitespace-nowrap px-4 py-3">{row.order_source}</td><td className="px-4 py-3">{row.order_count}</td><td className="whitespace-nowrap px-4 py-3">{money(row.accepted_total_minor)}</td><td className="whitespace-nowrap px-4 py-3">{money(row.discount_minor)}</td><td className="min-w-56 px-4 py-3 text-xs text-charcoal/75">{Object.entries({ PENDING_CONFIRMATION: row.state_pending_confirmation, CONFIRMED: row.state_confirmed, PROCESSING: row.state_processing, FULFILLED: row.state_fulfilled, COMPLETED: row.state_completed, CANCELLED: row.state_cancelled }).filter(([, count]) => count > 0).map(([state, count]) => `${state.replaceAll("_", " ")}: ${count}`).join(" · ") || "—"}</td>
          </tr>)}</tbody>
        </table>
        {report.rows.length === 0 && <p className="p-6 text-sm text-charcoal/75">No orders with attribution were placed in this period.</p>}
      </div>
      <p className="text-xs text-charcoal/75">State counts reflect each order’s current state. Order count and accepted values retain cancelled orders as historical intake.</p>
    </>}
  </div>;
}
