"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import { analyticsChoice, ANALYTICS_CHOICE_EVENT, initializeAnalytics, measurementId, setAnalyticsChoice, trackEvent, trackPageView } from "@/lib/analytics";

const subscribe = (callback: () => void) => {
  window.addEventListener(ANALYTICS_CHOICE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => { window.removeEventListener(ANALYTICS_CHOICE_EVENT, callback); window.removeEventListener("storage", callback); };
};
const serverChoice = () => "unset" as const;

export function useAnalyticsChoice() { return useSyncExternalStore(subscribe, analyticsChoice, serverChoice); }

export function AnalyticsControls() {
  const choice = useAnalyticsChoice();
  const [editing, setEditing] = useState(false);
  const pathname = usePathname();
  const id = measurementId();
  useEffect(() => {
    if (choice !== "accepted" || !initializeAnalytics()) return;
    trackPageView(pathname);
  }, [choice, pathname]);
  useEffect(() => {
    // Track the handoff without sending its destination phone number or message URL.
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element)?.closest?.("a[href]");
      if (!link || event.defaultPrevented) return;
      const href = link.getAttribute("href");
      if (!href) return;
      const url = new URL(href, window.location.origin);
      if (url.hostname !== "wa.me" && url.hostname !== "api.whatsapp.com") return;
      trackEvent("whatsapp_click", { page_path: pathname, enquiry_type: pathname.startsWith("/cart") ? "cart" : pathname.startsWith("/shop/") ? "product" : "general" });
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [pathname]);
  if (!id) return null;
  return <>
    <button type="button" className="fixed bottom-3 left-3 z-40 rounded-full border border-sand bg-cream px-3 py-2 text-xs text-charcoal shadow-sm" onClick={() => setEditing(true)}>Analytics settings</button>
    {(choice === "unset" || editing) && <section aria-label="Analytics preferences" className="fixed bottom-0 left-0 right-0 z-50 border-t border-sand bg-cream p-5 text-charcoal shadow-lg">
      <div className="container-page flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-2xl text-sm">May we use optional Google Analytics cookies to understand visits, product interest and WhatsApp clicks? Shopping works either way. <a href="/privacy" className="underline">Privacy details</a></p>
        <div className="flex gap-3"><button type="button" className="rounded-xl border border-charcoal px-5 py-3 text-sm" onClick={() => { setAnalyticsChoice("declined"); setEditing(false); }}>Decline analytics</button><button type="button" className="rounded-xl bg-charcoal px-5 py-3 text-sm text-cream" onClick={() => { setAnalyticsChoice("accepted"); setEditing(false); }}>Allow analytics</button></div>
      </div>
    </section>}
  </>;
}
