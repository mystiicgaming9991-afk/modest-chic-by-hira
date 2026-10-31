"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type DeliveryStatus = "PENDING" | "RETRY" | "PROCESSING" | "SENT" | "FAILED";
interface OutboxEvent {
  id: string;
  event_type: string;
  aggregate_type: string;
  status: DeliveryStatus;
  attempts: number;
  created_at: string;
  processed_at: string | null;
  next_attempt_at: string | null;
}
interface OutboxPage { items: OutboxEvent[]; total_count: number; limit: number; offset: number }

const STATUSES: DeliveryStatus[] = ["PENDING", "RETRY", "PROCESSING", "SENT", "FAILED"];
const formatTime = (value: string | null) => value ? new Date(value).toLocaleString() : "—";

export default function NotificationsAdminPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loadingIdentity, setLoadingIdentity] = useState(true);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState<OutboxPage | null>(null);
  const [status, setStatus] = useState<DeliveryStatus | "">("");
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      staffJson<StaffIdentity>("auth/me").then((staff) => {
        if (active) setIdentity(staff);
      }).catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      }).finally(() => {
        if (active) setLoadingIdentity(false);
      });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function load(offset = 0, selectedStatus = status) {
    const requestId = ++requestGeneration.current;
    setLoading(true);
    setError(null);
    setPage(null);
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (selectedStatus) params.set("status", selectedStatus);
    try {
      const result = await staffJson<OutboxPage>(`admin/notifications/outbox?${params}`);
      if (requestId === requestGeneration.current) setPage(result);
    } catch (cause) {
      if (requestId === requestGeneration.current) {
        setError(cause instanceof Error ? cause.message : "Email delivery status could not be loaded.");
      }
    } finally {
      if (requestId === requestGeneration.current) setLoading(false);
    }
  }

  useEffect(() => {
    if (!identity?.permission_keys.includes("notification.read")) return;
    const timer = window.setTimeout(() => void load(0), 0);
    return () => window.clearTimeout(timer);
    // The first page is loaded once after permission resolution.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity]);

  if (loadingIdentity) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("notification.read")) return <p role="alert">Notification access is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="mx-auto max-w-5xl space-y-6">
    <header><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Email delivery</h1><p className="mt-2 text-sm text-charcoal/75">Status for queued system emails. Recipients, message content, and encrypted credentials are not shown.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-sand bg-white p-5">
      <label className="text-sm font-medium">Delivery status<select value={status} disabled={loading} onChange={(event) => setStatus(event.target.value as DeliveryStatus | "")} className="mt-1 block min-w-48 rounded-lg border border-sand bg-white p-3 disabled:opacity-50"><option value="">All statuses</option>{STATUSES.map((entry) => <option key={entry} value={entry}>{entry}</option>)}</select></label>
      <button type="button" onClick={() => void load(0, status)} disabled={loading} className="rounded-lg bg-charcoal px-4 py-3 text-sm text-white disabled:opacity-50">{loading ? "Refreshing…" : "Refresh"}</button>
    </div>
    {status === "FAILED" && <p className="rounded-lg bg-warm-cream p-4 text-sm">Automatic delivery exhausted its retries. Start the corresponding fresh invitation, sign-in, or recovery flow instead of replaying a message that may contain an expired credential.</p>}
    <section className="overflow-x-auto rounded-2xl border border-sand bg-white">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-sand bg-cream/60 text-xs uppercase tracking-wide text-charcoal/75"><tr><th className="p-4">Event</th><th className="p-4">Flow</th><th className="p-4">Status</th><th className="p-4">Attempts</th><th className="p-4">Created</th><th className="p-4">Last / next action</th></tr></thead>
        <tbody className="divide-y divide-sand/70">{page?.items.map((event) => <tr key={event.id}>
          <td className="p-4 font-medium">{event.event_type}</td><td className="p-4">{event.aggregate_type.replaceAll("_", " ")}</td><td className="p-4">{event.status}</td><td className="p-4">{event.attempts}</td><td className="p-4">{formatTime(event.created_at)}</td><td className="p-4">{event.status === "SENT" ? `Sent ${formatTime(event.processed_at)}` : event.status === "FAILED" ? "No automatic retries remain" : event.status === "PROCESSING" ? "Delivery in progress" : `Next attempt ${formatTime(event.next_attempt_at)}`}</td>
        </tr>)}</tbody>
      </table>
      {page && page.items.length === 0 && <p className="p-6 text-sm text-charcoal/75">No email events match this status.</p>}
    </section>
    {page && <div className="flex items-center justify-between text-sm"><span>Showing {page.items.length ? page.offset + 1 : 0}–{page.offset + page.items.length} of {page.total_count}</span><div className="flex gap-2"><button type="button" disabled={loading || page.offset === 0} onClick={() => void load(Math.max(0, page.offset - page.limit))} className="rounded-lg border border-sand px-3 py-2 disabled:opacity-40">Previous</button><button type="button" disabled={loading || page.offset + page.items.length >= page.total_count} onClick={() => void load(page.offset + page.limit)} className="rounded-lg border border-sand px-3 py-2 disabled:opacity-40">Next</button></div></div>}
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}
