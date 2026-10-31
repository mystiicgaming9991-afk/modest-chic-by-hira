"use client";

import { useEffect, useRef, useState } from "react";

interface Review {
  id: string;
  rating: number;
  title: string | null;
  body: string | null;
  verified_purchase: boolean;
  created_at: string;
}

interface ReviewPage {
  review_count: number;
  average_rating: number;
  items: Review[];
  next_cursor: string | null;
}

export function ProductReviews({ slug }: { slug: string }) {
  const [loadedPage, setLoadedPage] = useState<{ slug: string; page: ReviewPage } | null>(null);
  const [errorSlug, setErrorSlug] = useState<string | null>(null);
  const [loadingMoreSlug, setLoadingMoreSlug] = useState<string | null>(null);
  const loadingMoreRequest = useRef(false);
  const requestGeneration = useRef(0);
  const page = loadedPage?.slug === slug ? loadedPage.page : null;
  const hasError = errorSlug === slug;
  const loadingMore = loadingMoreSlug === slug;

  useEffect(() => {
    const requestId = ++requestGeneration.current;
    let active = true;
    loadingMoreRequest.current = false;
    fetch(`/api/commerce/catalog/products/${encodeURIComponent(slug)}/reviews`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Reviews unavailable");
        return await response.json() as ReviewPage;
      })
      .then((result) => {
        if (active && requestId === requestGeneration.current) setLoadedPage({ slug, page: result });
      })
      .catch(() => {
        if (active && requestId === requestGeneration.current) setErrorSlug(slug);
      });
    return () => { active = false; };
  }, [slug]);

  async function loadMore() {
    if (!page?.next_cursor || loadingMoreRequest.current) return;
    const requestId = requestGeneration.current;
    loadingMoreRequest.current = true;
    setLoadingMoreSlug(slug);
    try {
      const response = await fetch(`/api/commerce/catalog/products/${encodeURIComponent(slug)}/reviews?after=${encodeURIComponent(page.next_cursor)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Reviews unavailable");
      const next = await response.json() as ReviewPage;
      if (requestId === requestGeneration.current) {
        setLoadedPage((current) => current?.slug === slug
          ? { slug, page: { ...next, items: [...current.page.items, ...next.items] } }
          : current);
      }
    } catch {
      if (requestId === requestGeneration.current) setErrorSlug(slug);
    } finally {
      if (requestId === requestGeneration.current) {
        loadingMoreRequest.current = false;
        setLoadingMoreSlug(null);
      }
    }
  }

  return <section aria-labelledby="product-reviews" className="mt-16 border-t border-sand/60 pt-10">
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <div><p className="label-text text-terracotta">Customer feedback</p><h2 id="product-reviews" className="heading-md mt-2 text-charcoal">Reviews</h2></div>
      {page && <p className="text-sm text-charcoal/75">{page.review_count} {page.review_count === 1 ? "review" : "reviews"}{page.review_count > 0 ? ` · ${page.average_rating.toFixed(1)} out of 5` : ""}</p>}
    </div>
    {hasError ? <p className="mt-5 text-sm text-charcoal/75">Reviews are temporarily unavailable.</p>
      : !page ? <p role="status" className="mt-5 text-sm text-charcoal/75">Loading reviews…</p>
      : page.items.length === 0 ? <p className="mt-5 text-sm text-charcoal/75">No approved reviews yet.</p>
      : <><ul className="mt-5 divide-y divide-sand/60">{page.items.map((review) => <li key={review.id} className="py-5 first:pt-0">
        <div className="flex flex-wrap items-center gap-2"><span aria-label={`${review.rating} out of 5 stars`} className="text-terracotta">{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</span>{review.verified_purchase && <span className="rounded-full bg-warm-cream px-2.5 py-1 text-xs text-charcoal/75">Verified purchase</span>}</div>
        {review.title && <h3 className="mt-2 font-medium text-charcoal">{review.title}</h3>}
        {review.body && <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-charcoal/70">{review.body}</p>}
      </li>)}</ul>{page.next_cursor && <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="mt-4 rounded-full border border-charcoal px-5 py-2 text-sm disabled:opacity-50">{loadingMore ? "Loading…" : "More reviews"}</button>}</>}
  </section>;
}
