"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { staffJson } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

interface Review {
  id: string;
  product_title: string;
  order_number: string | null;
  rating: number;
  title: string | null;
  body: string | null;
  created_at: string;
}

interface ReviewPage {
  items: Review[];
  total_count: number;
  limit: number;
  offset: number;
}

export default function ReviewModerationPage() {
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const loadedCount = useRef(0);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const queueRequest = useRef(0);

  const load = useCallback(async (append = false) => {
    const requestId = ++queueRequest.current;
    if (!append) setLoading(true);
    else setLoadingMore(true);
    try {
      const identity = await staffJson<{ permission_keys: string[] }>("auth/me");
      if (requestId !== queueRequest.current) return;
      if (!identity.permission_keys.includes("review.moderate")) {
        setError("Your staff account does not have permission to moderate reviews.");
        return;
      }
      const offset = append ? loadedCount.current : 0;
      const page = await staffJson<ReviewPage>(`admin/reviews?limit=100&offset=${offset}`);
      if (requestId !== queueRequest.current) return;
      setReviews((current) => append ? [...current, ...page.items] : page.items);
      loadedCount.current = offset + page.items.length;
      setTotalCount(page.total_count);
      setError(null);
    } catch (cause) {
      if (requestId === queueRequest.current) {
        setError(cause instanceof Error ? cause.message : "Review queue could not be loaded.");
        if (!append) { setReviews([]); setTotalCount(0); loadedCount.current = 0; }
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
      }
    } finally {
      if (requestId === queueRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [router]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function moderate(review: Review, status: "APPROVED" | "REJECTED") {
    const reason = reasons[review.id]?.trim() ?? "";
    if (reason.length < 3) { setError("Enter a moderation reason of at least 3 characters."); return; }
    setBusyId(review.id); setError(null); setNotice(null);
    try {
      await staffJson(`admin/reviews/${review.id}/moderate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, reason }),
      });
      setNotice(`Review ${status.toLowerCase()}.`);
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Review could not be moderated."); }
    finally { setBusyId(null); }
  }

  return <div className="space-y-6">
    <div><Link href="/admin" className="text-sm text-terracotta underline">← Staff workspace</Link><p className="mt-5 text-xs uppercase tracking-widest text-terracotta">Moderation</p><h1 className="heading-md mt-2">Product reviews</h1><p className="mt-2 text-sm text-charcoal/75">Approve or reject purchase reviews. The reason is retained in the moderation history.</p></div>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    {loading ? <p role="status">Loading review queue…</p> : reviews.length === 0 ? <p className="rounded-2xl border border-sand bg-white p-6 text-sm text-charcoal/75">There are no pending reviews.</p> : <><p className="text-sm text-charcoal/75">Showing {reviews.length} of {totalCount} pending reviews.</p><div className="space-y-4">{reviews.map((review) => <article key={review.id} className="space-y-4 rounded-2xl border border-sand bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-medium">{review.product_title}</h2><p className="mt-1 text-sm text-charcoal/75">{review.order_number ? `Order ${review.order_number}` : "Purchase record unavailable"} · {review.rating}/5 · {new Date(review.created_at).toLocaleDateString()}</p></div><span className="rounded-full bg-warm-cream px-3 py-1 text-xs">Pending</span></div>
      {review.title && <h3 className="font-medium">{review.title}</h3>}{review.body && <p className="whitespace-pre-wrap text-sm leading-relaxed text-charcoal/75">{review.body}</p>}
      <label className="block text-sm font-medium">Moderation reason<textarea required minLength={3} maxLength={2000} value={reasons[review.id] ?? ""} onChange={(event) => setReasons((current) => ({ ...current, [review.id]: event.target.value }))} rows={2} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <div className="flex gap-3"><button disabled={busyId === review.id} onClick={() => void moderate(review, "APPROVED")} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Approve</button><button disabled={busyId === review.id} onClick={() => void moderate(review, "REJECTED")} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-50">Reject</button></div>
    </article>)}</div>{reviews.length < totalCount && <button type="button" onClick={() => void load(true)} disabled={loading || loadingMore || busyId !== null} className="rounded-full border border-charcoal px-5 py-2 text-sm disabled:opacity-50">{loadingMore ? "Loading…" : "Load more reviews"}</button>}</>}
  </div>;
}
