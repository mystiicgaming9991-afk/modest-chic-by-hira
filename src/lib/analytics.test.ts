import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  document.getElementById("mc-ga4")?.remove();
  Object.assign(window, { dataLayer: undefined, gtag: undefined });
});
afterEach(() => vi.unstubAllEnvs());

describe("optional GA4 analytics", () => {
  it("does not load or collect without a valid ID and visitor choice", async () => {
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "");
    const analytics = await import("./analytics");
    analytics.setAnalyticsChoice("accepted");
    expect(analytics.initializeAnalytics()).toBe(false);
    expect(document.getElementById("mc-ga4")).toBeNull();
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "G-TEST123");
    analytics.setAnalyticsChoice("declined");
    expect(analytics.initializeAnalytics()).toBe(false);
    analytics.trackEvent("whatsapp_click");
    expect(document.getElementById("mc-ga4")).toBeNull();
  });
  it("loads once after acceptance and stops collecting when declined", async () => {
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "G-TEST123");
    const analytics = await import("./analytics");
    analytics.setAnalyticsChoice("accepted");
    expect(analytics.initializeAnalytics()).toBe(true);
    expect(analytics.initializeAnalytics()).toBe(true);
    expect(document.querySelectorAll("#mc-ga4")).toHaveLength(1);
    const gtag = vi.fn();
    Object.assign(window, { gtag });
    analytics.trackEvent("add_to_cart", { currency: "PKR", value: 1500 });
    expect(gtag).toHaveBeenCalledWith("event", "add_to_cart", expect.objectContaining({ currency: "PKR", value: 1500 }));
    analytics.setAnalyticsChoice("declined");
    gtag.mockClear();
    analytics.trackEvent("whatsapp_click");
    expect(gtag).not.toHaveBeenCalled();
  });
  it("strips URL queries from page views and recognises Instagram traffic", async () => {
    vi.stubEnv("NEXT_PUBLIC_GA_MEASUREMENT_ID", "G-TEST123");
    window.history.replaceState(null, "", "/shop/?q=private@example.com&utm_source=instagram");
    const analytics = await import("./analytics");
    analytics.setAnalyticsChoice("accepted");
    analytics.initializeAnalytics();
    const gtag = vi.fn();
    Object.assign(window, { gtag });
    analytics.trackPageView("/shop/");
    expect(gtag).toHaveBeenCalledWith("event", "page_view", expect.objectContaining({ page_location: `${window.location.origin}/shop/`, campaign_source: "instagram" }));
    expect(JSON.stringify(gtag.mock.calls)).not.toContain("private@example.com");
    window.history.replaceState(null, "", "/");
  });
});
