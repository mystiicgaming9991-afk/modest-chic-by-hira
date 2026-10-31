import type { Product, ProductVariant } from "@/lib/data";

export const ANALYTICS_CHOICE_KEY = "mc_analytics_choice_v1";
export const ANALYTICS_CHOICE_EVENT = "mc-analytics-choice";
export type AnalyticsChoice = "accepted" | "declined" | "unset";

type AnalyticsWindow = Window & {
  dataLayer?: unknown[];
  gtag?: (...args: unknown[]) => void;
};
let initializedId: string | null = null;

export function measurementId(): string | null {
  const id = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
  return id && /^G-[A-Z0-9]+$/.test(id) ? id : null;
}

export function analyticsChoice(): AnalyticsChoice {
  if (typeof window === "undefined") return "unset";
  try {
    const choice = localStorage.getItem(ANALYTICS_CHOICE_KEY);
    return choice === "accepted" || choice === "declined" ? choice : "unset";
  } catch { return "unset"; }
}

export function setAnalyticsChoice(choice: "accepted" | "declined") {
  try { localStorage.setItem(ANALYTICS_CHOICE_KEY, choice); } catch { /* If storage fails, tracking remains disabled. */ }
  const id = measurementId();
  if (id) {
    Object.assign(window, { [`ga-disable-${id}`]: choice !== "accepted" });
    if (choice === "accepted" && initializedId === id) (window as AnalyticsWindow).gtag?.("consent", "update", { analytics_storage: "granted" });
    if (choice === "declined") {
      (window as AnalyticsWindow).gtag?.("consent", "update", { analytics_storage: "denied" });
      for (const cookie of document.cookie.split(";")) {
        const name = cookie.trim().split("=")[0];
        if (name === "_ga" || name.startsWith("_ga_")) {
          document.cookie = `${name}=; Max-Age=0; Path=/`;
          const labels = window.location.hostname.split(".");
          for (let index = 0; index < labels.length - 1; index++) document.cookie = `${name}=; Max-Age=0; Path=/; Domain=.${labels.slice(index).join(".")}`;
        }
      }
    }
  }
  window.dispatchEvent(new Event(ANALYTICS_CHOICE_EVENT));
}

export function initializeAnalytics(): boolean {
  const id = measurementId();
  if (!id || analyticsChoice() !== "accepted") return false;
  const target = window as AnalyticsWindow;
  Object.assign(window, { [`ga-disable-${id}`]: false });
  if (initializedId === id) return true;
  target.dataLayer = target.dataLayer ?? [];
  target.gtag = function () {
    // Google tag commands use the standard arguments-object queue format.
    // eslint-disable-next-line prefer-rest-params
    target.dataLayer!.push(arguments);
  };
  target.gtag("consent", "default", { analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" });
  target.gtag("js", new Date());
  target.gtag("config", id, { send_page_view: false, page_location: `${window.location.origin}${window.location.pathname}`, page_referrer: safeReferrer(), allow_google_signals: false, allow_ad_personalization_signals: false, cookie_domain: "none" });
  const script = document.createElement("script");
  script.id = "mc-ga4";
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(script);
  initializedId = id;
  return true;
}

type EventName = "page_view" | "view_item" | "view_cart" | "add_to_cart" | "remove_from_cart" | "whatsapp_click";
export function trackEvent(name: EventName, values: Record<string, unknown> = {}) {
  const id = measurementId();
  if (!id || analyticsChoice() !== "accepted" || !initializeAnalytics()) return;
  // Never pass full WhatsApp links, prepared messages, form fields or search text here.
  (window as AnalyticsWindow).gtag?.("event", name, { ...values, page_location: `${window.location.origin}${window.location.pathname}`, page_referrer: safeReferrer(), transport_type: "beacon" });
}

export function trackPageView(pathname: string) {
  const source = new URLSearchParams(window.location.search).get("utm_source");
  trackEvent("page_view", {
    page_location: `${window.location.origin}${pathname}`,
    page_title: document.title,
    page_referrer: safeReferrer(),
    ...(source === "instagram" ? { campaign_source: "instagram", campaign_medium: "social" } : {}),
  });
}
function safeReferrer(): string {
  try { return new URL(document.referrer).origin; } catch { return ""; }
}

export function analyticsItem(product: Product, variant: ProductVariant, quantity: number) {
  return { item_id: variant.sku || variant.id, item_name: product.title, item_variant: variant.name, item_category: product.category, price: variant.salePrice ?? variant.price, quantity };
}
export function trackProductEvent(name: "view_item" | "add_to_cart" | "remove_from_cart", product: Product, variant: ProductVariant, quantity: number) {
  if (quantity <= 0) return;
  trackEvent(name, { currency: "PKR", value: (variant.salePrice ?? variant.price) * quantity, items: [analyticsItem(product, variant, quantity)] });
}
