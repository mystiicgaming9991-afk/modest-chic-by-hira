"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronRight,
  ArrowLeft,
  ShieldCheck,
  Truck,
  MapPin,
  CreditCard,
  Banknote,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCart } from "@/lib/context/cart-context";
import { useCatalog } from "@/lib/context/catalog-context";

type Step = "shipping" | "payment" | "review";

interface FormData {
  name: string;
  phone: string;
  email: string;
  address: string;
  area: string;
  city: string;
  postalCode: string;
  deliveryNotes: string;
  fulfillmentMethod: "delivery" | "pickup";
  paymentMethod: "cod" | "online";
}

interface Quote {
  cart_version: number;
  subtotal_minor: number;
  shipping_charge_minor: number;
  discount_minor: number;
  total_minor: number;
  policy_version_ids: Record<"checkout_bundle" | "shipping" | "returns", string>;
  policies: Record<"checkout_bundle" | "shipping" | "returns", {
    policy_version_id: string;
    version: number;
    content: Record<string, unknown>;
  }>;
  idempotency_key: string;
  applied_coupon: { code: string; discount_minor: number } | null;
  items: Array<{
    product_title: string;
    variant_name: string;
    quantity: number;
    line_total_minor: number;
  }>;
}

interface SavedCheckoutAttempt {
  version: 1;
  saved_at: number;
  quote: Quote;
  form_data: FormData;
  accepted_policy: boolean;
  coupon_code: string;
}

const CHECKOUT_RECOVERY_KEY = "mc_checkout_recovery_v1";
const CHECKOUT_RECOVERY_TTL = 7 * 24 * 60 * 60 * 1000;

function isSavedCheckoutAttempt(value: unknown): value is SavedCheckoutAttempt {
  if (!value || typeof value !== "object") return false;
  const saved = value as Partial<SavedCheckoutAttempt>;
  const form = saved.form_data;
  const quote = saved.quote;
  return saved.version === 1
    && typeof saved.saved_at === "number"
    && Number.isFinite(saved.saved_at)
    && saved.saved_at <= Date.now()
    && Date.now() - saved.saved_at < CHECKOUT_RECOVERY_TTL
    && !!form
    && typeof form.name === "string"
    && typeof form.phone === "string"
    && typeof form.email === "string"
    && typeof form.address === "string"
    && typeof form.area === "string"
    && typeof form.city === "string"
    && typeof form.postalCode === "string"
    && typeof form.deliveryNotes === "string"
    && (form.fulfillmentMethod === "delivery" || form.fulfillmentMethod === "pickup")
    && (form.paymentMethod === "cod" || form.paymentMethod === "online")
    && !!quote
    && typeof quote.idempotency_key === "string"
    && quote.idempotency_key.length >= 16
    && typeof quote.cart_version === "number"
    && typeof quote.total_minor === "number"
    && !!quote.policy_version_ids
    && ["checkout_bundle", "shipping", "returns"].every((type) =>
      typeof quote.policy_version_ids[type as keyof Quote["policy_version_ids"]] === "string")
    && !!quote.policies
    && ["checkout_bundle", "shipping", "returns"].every((type) => {
      const policy = quote.policies?.[type as keyof Quote["policies"]];
      return !!policy
        && typeof policy.policy_version_id === "string"
        && typeof policy.version === "number"
        && !!policy.content
        && typeof policy.content === "object"
        && !Array.isArray(policy.content);
    })
    && typeof saved.accepted_policy === "boolean"
    && typeof saved.coupon_code === "string"
    && Array.isArray(quote.items)
    && quote.items.every((item) => typeof item.product_title === "string"
      && typeof item.variant_name === "string"
      && typeof item.quantity === "number"
      && typeof item.line_total_minor === "number");
}

function saveCheckoutAttempt(attempt: SavedCheckoutAttempt) {
  try {
    window.sessionStorage.setItem(CHECKOUT_RECOVERY_KEY, JSON.stringify(attempt));
  } catch {
    // Storage is a recovery aid; a browser storage failure must not block checkout.
  }
}

function clearCheckoutAttempt() {
  try {
    window.sessionStorage.removeItem(CHECKOUT_RECOVERY_KEY);
  } catch {
    // Ignore storage failures while preserving the checkout flow.
  }
}

interface CheckoutOptions {
  delivery_cities: string[];
  pickup_cities: string[];
  delivery_fee_minor: number | null;
  payment_methods: string[];
}

export default function CheckoutPage() {
  const router = useRouter();
  const { mode } = useCatalog();
  const [step, setStep] = useState<Step>("shipping");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [options, setOptions] = useState<CheckoutOptions | null>(null);
  const [acceptedPolicy, setAcceptedPolicy] = useState(false);
  const [couponCode, setCouponCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [recoveryReady, setRecoveryReady] = useState(false);
  const [recoveredAttempt, setRecoveredAttempt] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormData>({
    name: "",
    phone: "",
    email: "",
    address: "",
    area: "",
    city: "Karachi",
    postalCode: "",
    deliveryNotes: "",
    fulfillmentMethod: "delivery",
    paymentMethod: "cod",
  });
  const hasRecoveredAttempt = useRef(false);

  // Real cart data
  const { subtotal, getAllLines, formatPrice: fmtPrice, refreshCart } = useCart();
  const cartLines = getAllLines();

  useEffect(() => {
    let restored: SavedCheckoutAttempt | null = null;
    try {
      const raw = window.sessionStorage.getItem(CHECKOUT_RECOVERY_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as unknown;
        if (isSavedCheckoutAttempt(saved)) {
          restored = saved;
          hasRecoveredAttempt.current = true;
        } else {
          clearCheckoutAttempt();
        }
      }
    } catch {
      clearCheckoutAttempt();
    }
    queueMicrotask(() => {
      if (restored) {
        setQuote(restored.quote);
        setFormData(restored.form_data);
        setAcceptedPolicy(restored.accepted_policy);
        setCouponCode(restored.coupon_code);
        setStep("review");
        setRecoveredAttempt(true);
      }
      setRecoveryReady(true);
    });
  }, []);

  useEffect(() => {
    if (!recoveryReady || mode !== "live") return;
    if (!quote) {
      clearCheckoutAttempt();
      return;
    }
    const saved: SavedCheckoutAttempt = {
      version: 1,
      saved_at: Date.now(),
      quote,
      form_data: formData,
      accepted_policy: acceptedPolicy,
      coupon_code: couponCode,
    };
    saveCheckoutAttempt(saved);
  }, [acceptedPolicy, couponCode, formData, mode, quote, recoveryReady]);

  useEffect(() => {
    if (mode !== "live") return;
    let active = true;
    fetch("/api/commerce/checkout/options", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.message ?? "Checkout options could not be loaded.");
        return body as CheckoutOptions;
      })
      .then((body) => {
        if (!active) return;
        setOptions(body);
        if (!hasRecoveredAttempt.current) {
          const method = body.delivery_cities.length ? "delivery" : "pickup";
          const city = (method === "delivery" ? body.delivery_cities : body.pickup_cities)[0] ?? "";
          setFormData((current) => ({ ...current, fulfillmentMethod: method, city }));
        }
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Checkout options could not be loaded."); });
    return () => { active = false; };
  }, [mode]);

  const cities = mode === "live"
    ? (formData.fulfillmentMethod === "delivery" ? options?.delivery_cities : options?.pickup_cities) ?? []
    : ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Peshawar", "Quetta", "Multan"];

  const shippingCost =
    formData.fulfillmentMethod === "pickup"
      ? 0
      : subtotal >= 3000
      ? 0
      : 250;
  const total = mode === "live" && quote ? quote.total_minor / 100 : subtotal + shippingCost;

  const updateField = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setQuote(null);
    setAcceptedPolicy(false);
    setRecoveredAttempt(false);
    setError(null);
  };

  const chooseFulfillment = (method: "delivery" | "pickup") => {
    const availableCities = method === "delivery" ? options?.delivery_cities : options?.pickup_cities;
    setFormData((current) => ({ ...current, fulfillmentMethod: method, city: mode === "live" ? availableCities?.[0] ?? "" : current.city }));
    setQuote(null);
    setAcceptedPolicy(false);
    setRecoveredAttempt(false);
    setError(null);
  };

  const handleSubmit = async () => {
    if (mode === "live") {
      setSubmitting(true);
      setError(null);
      try {
        const response = await fetch("/api/commerce/checkout/quote", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            fulfillment_method: formData.fulfillmentMethod.toUpperCase(),
            city: formData.city,
            coupon_code: couponCode.trim() || null,
          }),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.message ?? "Could not review the order.");
        setQuote(body as Quote);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not review the order.");
        setSubmitting(false);
        return;
      }
      setSubmitting(false);
    }
    setStep("review");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const placeOrder = async () => {
    if (!quote || !acceptedPolicy || submitting) return;
    setSubmitting(true);
    setError(null);
    const requestBody = {
      checkout_id: quote.idempotency_key,
      cart_version: quote.cart_version,
      accepted_total_minor: quote.total_minor,
      policy_version_ids: quote.policy_version_ids,
      accepted_policy: acceptedPolicy,
      coupon_code: quote.applied_coupon?.code ?? null,
      customer_name: formData.name,
      customer_phone: formData.phone,
      customer_email: formData.email || null,
      fulfillment_method: formData.fulfillmentMethod.toUpperCase(),
      payment_method: formData.paymentMethod.toUpperCase(),
      address_line1: formData.fulfillmentMethod === "delivery" ? formData.address : null,
      address_area: formData.fulfillmentMethod === "delivery" ? formData.area : null,
      address_city: formData.city,
      address_postal_code: formData.postalCode || null,
      delivery_notes: formData.deliveryNotes || null,
    };
    try {
      const savedAttempt: SavedCheckoutAttempt = {
        version: 1,
        saved_at: Date.now(),
        quote,
        form_data: formData,
        accepted_policy: acceptedPolicy,
        coupon_code: couponCode,
      };
      saveCheckoutAttempt(savedAttempt);
      const response = await fetch("/api/commerce/checkout/orders", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const body = await response.json();
      if (!response.ok) {
        if (response.status === 409 && ["CART_CHANGED", "POLICY_CHANGED", "QUOTE_CHANGED", "COUPON_CHANGED", "INSUFFICIENT_STOCK"].includes(body.code)) {
          clearCheckoutAttempt();
          setQuote(null);
          setAcceptedPolicy(false);
          setRecoveredAttempt(false);
          setStep("shipping");
        }
        throw new Error(body.message ?? "Could not place the order.");
      }
      clearCheckoutAttempt();
      void refreshCart();
      router.push(`/order-confirmation?order=${encodeURIComponent(body.order_id)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not place the order. Retry with the same request.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-cream min-h-screen">
      <div className="container-page py-8 md:py-12">
        {mode === "preview" && <div role="status" className="mb-8 rounded-2xl border border-terracotta/30 bg-[#f4ebe6] p-5 text-charcoal">
          <p className="font-medium">Checkout preview</p>
          <p className="mt-1 text-sm text-charcoal/70">Ordering is not connected yet. Details entered here stay in this browser and no payment or order will be submitted.</p>
        </div>}
        {mode === "live" && options && !options.delivery_cities.length && !options.pickup_cities.length && <div role="status" className="mb-8 rounded-2xl border border-sand bg-white p-5 text-charcoal">Checkout is currently unavailable.</div>}
        {error && <div role="alert" className="mb-8 rounded-2xl border border-rust/30 bg-rust/10 p-5 text-rust">{error}</div>}
        {recoveredAttempt && <div role="status" className="mb-8 rounded-2xl border border-terracotta/30 bg-[#f4ebe6] p-5 text-charcoal"><p className="font-medium">Checkout attempt restored</p><p className="mt-1 text-sm text-charcoal/70">If your previous request reached us, retrying the same order will recover its confirmation without creating a duplicate.</p></div>}
        {mode === "live" && <p className="mb-6 text-sm text-charcoal/70">Have an account? <Link href="/account" className="text-terracotta underline">Sign in before placing your order</Link> to save it to your history. You can also continue as a guest.</p>}
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-charcoal/75 mb-8">
          <Link href="/" className="hover:text-charcoal transition-colors">
            Home
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <Link href="/cart" className="hover:text-charcoal transition-colors">
            Cart
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="text-charcoal/70">Checkout</span>
        </nav>

        {/* Progress Steps */}
        <div className="flex items-center justify-center mb-12">
          {[
            { key: "shipping", label: "Shipping" },
            { key: "payment", label: "Payment" },
            { key: "review", label: "Review" },
          ].map((s, idx) => (
            <div key={s.key} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                  step === s.key
                    ? "bg-charcoal text-cream"
                    : step === "review" && ["shipping", "payment"].includes(s.key)
                    ? "bg-terracotta text-cream"
                    : "bg-warm-cream text-charcoal/75"
                }`}
              >
                {(step === "review" && ["shipping", "payment"].includes(s.key)) ? (
                  <Check className="w-4 h-4" />
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={`hidden sm:block ml-2 text-sm ${
                  step === s.key
                    ? "text-charcoal font-medium"
                    : "text-charcoal/75"
                }`}
              >
                {s.label}
              </span>
              {idx < 2 && (
                <div className="w-8 sm:w-16 h-px bg-sand mx-2 sm:mx-4" />
              )}
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-10">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {step === "shipping" && (
              <div className="space-y-8 animate-fade-in-up">
                <div>
                  <h2 className="heading-md text-charcoal mb-6">
                    Shipping Information
                  </h2>

                  {/* Fulfillment Method */}
                  <div className="grid grid-cols-2 gap-3 mb-8">
                    {[
                      {
                        value: "delivery" as const,
                        icon: Truck,
                        label: "Home Delivery",
                        desc: mode === "live" ? "Available in selected cities" : "Preview delivery option",
                      },
                      {
                        value: "pickup" as const,
                        icon: MapPin,
                        label: "Store Pickup",
                        desc: mode === "live" ? "Available in selected cities" : "Preview pickup option",
                      },
                    ].map((method) => (
                      <button
                        key={method.value}
                        onClick={() => chooseFulfillment(method.value)}
                        disabled={mode === "live" && !(method.value === "delivery" ? options?.delivery_cities.length : options?.pickup_cities.length)}
                        className={`p-4 rounded-xl border-2 text-left transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
                          formData.fulfillmentMethod === method.value
                            ? "border-charcoal bg-charcoal/5"
                            : "border-sand/50 hover:border-sand"
                        }`}
                      >
                        <method.icon
                          className={`w-5 h-5 mb-2 ${
                            formData.fulfillmentMethod === method.value
                              ? "text-charcoal"
                              : "text-charcoal/75"
                          }`}
                        />
                        <p className="text-sm font-medium text-charcoal">
                          {method.label}
                        </p>
                        <p className="text-xs text-charcoal/75 mt-0.5">
                          {method.desc}
                        </p>
                      </button>
                    ))}
                  </div>

                  {/* Contact */}
                  <div className="space-y-4">
                    {mode === "live" && <div>
                      <label htmlFor="checkout-coupon" className="block text-sm font-medium text-charcoal mb-1.5">Promotion code <span className="font-normal text-charcoal/75">(optional)</span></label>
                      <input id="checkout-coupon" type="text" autoComplete="off" maxLength={100} value={couponCode} onChange={(event) => { setCouponCode(event.target.value); setQuote(null); setAcceptedPolicy(false); }} placeholder="Enter a promotion code" className="w-full rounded-xl border border-sand bg-white px-4 py-3 text-sm text-charcoal" />
                    </div>}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="checkout-name" className="block text-sm font-medium text-charcoal mb-1.5">
                          Full Name *
                        </label>
                        <input
                          id="checkout-name"
                          type="text"
                          required
                          value={formData.name}
                          onChange={(e) => updateField("name", e.target.value)}
                          placeholder="Your full name"
                          className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                        />
                      </div>
                      <div>
                        <label htmlFor="checkout-phone" className="block text-sm font-medium text-charcoal mb-1.5">
                          Phone Number *
                        </label>
                        <input
                          id="checkout-phone"
                          type="tel"
                          required
                          value={formData.phone}
                          onChange={(e) => updateField("phone", e.target.value)}
                          placeholder="03XX-XXXXXXX"
                          className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                        />
                      </div>
                    </div>
                    <div>
                      <label htmlFor="checkout-email" className="block text-sm font-medium text-charcoal mb-1.5">
                        Email{" "}
                        <span className="text-charcoal/75 font-normal">
                          (optional)
                        </span>
                      </label>
                      <input
                        id="checkout-email"
                        type="email"
                        value={formData.email}
                        onChange={(e) => updateField("email", e.target.value)}
                        placeholder="you@example.com"
                        className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                      />
                    </div>
                  </div>

                  {formData.fulfillmentMethod === "pickup" && <div className="mt-6">
                    <label htmlFor="checkout-city" className="mb-1.5 block text-sm font-medium text-charcoal">Pickup city</label>
                    <select id="checkout-city" value={formData.city} onChange={(event) => updateField("city", event.target.value)} className="w-full rounded-xl border border-sand bg-white px-4 py-3 text-sm text-charcoal">
                      {cities.map((city) => <option key={city}>{city}</option>)}
                    </select>
                  </div>}

                  {/* Address (if delivery) */}
                  {formData.fulfillmentMethod === "delivery" && (
                    <div className="space-y-4 mt-6">
                      <div>
                        <label htmlFor="checkout-address" className="block text-sm font-medium text-charcoal mb-1.5">
                          Address *
                        </label>
                        <input
                          id="checkout-address"
                          type="text"
                          required
                          value={formData.address}
                          onChange={(e) =>
                            updateField("address", e.target.value)
                          }
                          placeholder="House/flat number, street"
                          className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                        />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="checkout-area" className="block text-sm font-medium text-charcoal mb-1.5">
                            Area *
                          </label>
                          <input
                            id="checkout-area"
                            type="text"
                            required
                            value={formData.area}
                            onChange={(e) =>
                              updateField("area", e.target.value)
                            }
                            placeholder="Gulshan, DHA, etc."
                            className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                          />
                        </div>
                        <div>
                          <label htmlFor="checkout-city" className="block text-sm font-medium text-charcoal mb-1.5">
                            City *
                          </label>
                          <select
                            id="checkout-city"
                            value={formData.city}
                            onChange={(e) =>
                              updateField("city", e.target.value)
                            }
                            className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                          >
                            {cities.map((city) => <option key={city}>{city}</option>)}
                          </select>
                        </div>
                      </div>
                      <div>
                        <label htmlFor="checkout-delivery-notes" className="block text-sm font-medium text-charcoal mb-1.5">
                          Delivery Notes{" "}
                          <span className="text-charcoal/75 font-normal">
                            (optional)
                          </span>
                        </label>
                        <textarea
                          id="checkout-delivery-notes"
                          value={formData.deliveryNotes}
                          onChange={(e) =>
                            updateField("deliveryNotes", e.target.value)
                          }
                          placeholder="Landmark, building color, delivery instructions..."
                          rows={2}
                          className="w-full px-4 py-3 text-sm bg-white border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all resize-none"
                        />
                      </div>
                    </div>
                  )}
                </div>

                    <div className="flex justify-between pt-4">
                  <Link
                    href="/cart"
                    className="inline-flex items-center gap-1 text-sm text-charcoal/75 hover:text-terracotta transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Cart
                  </Link>
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => setStep("payment")}
                    disabled={
                      (mode === "live" && (!options || !formData.city)) ||
                      !formData.name ||
                      !formData.phone ||
                      (formData.fulfillmentMethod === "delivery" &&
                        (!formData.address || !formData.area))
                    }
                  >
                    Continue to Payment
                  </Button>
                </div>
              </div>
            )}

            {step === "payment" && (
              <div className="space-y-8 animate-fade-in-up">
                <div>
                  <h2 className="heading-md text-charcoal mb-6">
                    Payment Method
                  </h2>

                  <div className="space-y-3">
                    {[
                      {
                        value: "cod" as const,
                        icon: Banknote,
                        label: "Cash on Delivery",
                        desc: "Proposed payment option",
                      },
                      {
                        value: "online" as const,
                        icon: CreditCard,
                        label: "Online Payment",
                        desc: "Online payment is not available yet",
                      },
                    ].map((method) => (
                      <button
                        key={method.value}
                        onClick={() => updateField("paymentMethod", method.value)}
                        disabled={method.value === "online"}
                        className={`w-full p-5 rounded-xl border-2 text-left transition-all flex items-start gap-4 ${
                          formData.paymentMethod === method.value
                            ? "border-charcoal bg-charcoal/5"
                            : "border-sand/50 hover:border-sand"
                        } ${method.value === "online" ? "cursor-not-allowed opacity-50" : ""}`}
                      >
                        <div
                          className={`p-2.5 rounded-xl ${
                            formData.paymentMethod === method.value
                              ? "bg-charcoal text-cream"
                              : "bg-warm-cream text-charcoal/75"
                          }`}
                        >
                          <method.icon className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-charcoal">
                            {method.label}
                          </p>
                          <p className="text-xs text-charcoal/75 mt-0.5">
                            {method.desc}
                          </p>
                        </div>
                        <div
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center mt-1 ${
                            formData.paymentMethod === method.value
                              ? "border-charcoal bg-charcoal"
                              : "border-sand"
                          }`}
                        >
                          {formData.paymentMethod === method.value && (
                            <Check className="w-3 h-3 text-cream" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>

                  {formData.paymentMethod === "cod" && (
                    <div className="mt-6 p-4 bg-warm-cream rounded-xl">
                      <p className="text-sm text-charcoal/75">
                        {mode === "live" ? "Pay in cash when your order is delivered." : "Cash on delivery is shown for preview. Ordering is not open yet."}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex justify-between pt-4">
                  <button
                    onClick={() => setStep("shipping")}
                    className="inline-flex items-center gap-1 text-sm text-charcoal/75 hover:text-terracotta transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Shipping
                  </button>
                  <Button variant="primary" size="lg" onClick={() => void handleSubmit()} disabled={submitting || mode === "loading" || mode === "error" || (mode === "live" && (!options || !formData.city))}>
                    {submitting ? "Checking…" : "Review Order"}
                  </Button>
                </div>
              </div>
            )}

            {step === "review" && (
              <div className="space-y-8 animate-fade-in-up">
                <div>
                  <h2 className="heading-md text-charcoal mb-6">
                    Review Order
                  </h2>

                  {/* Shipping Review */}
                  <div className="bg-white rounded-xl border border-sand/50 p-5 mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-charcoal flex items-center gap-2">
                        <Truck className="w-4 h-4 text-charcoal/75" />
                        Shipping Details
                      </h3>
                      <button
                        onClick={() => setStep("shipping")}
                        className="text-xs text-terracotta hover:text-rust"
                      >
                        Edit
                      </button>
                    </div>
                    <div className="text-sm text-charcoal/75 space-y-1">
                      <p>{formData.name}</p>
                      <p>{formData.phone}</p>
                      {formData.email && <p>{formData.email}</p>}
                      {formData.fulfillmentMethod === "delivery" ? (
                        <>
                          <p>{formData.address}</p>
                          <p>
                            {formData.area}, {formData.city}
                          </p>
                        </>
                      ) : (
                        <p>Store Pickup — {formData.city}</p>
                      )}
                    </div>
                  </div>

                  {/* Payment Review */}
                  <div className="bg-white rounded-xl border border-sand/50 p-5 mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-charcoal flex items-center gap-2">
                        <Banknote className="w-4 h-4 text-charcoal/75" />
                        Payment Method
                      </h3>
                      <button
                        onClick={() => setStep("payment")}
                        className="text-xs text-terracotta hover:text-rust"
                      >
                        Edit
                      </button>
                    </div>
                    <p className="text-sm text-charcoal/75">
                      {formData.paymentMethod === "cod"
                        ? "Cash on Delivery"
                        : "Online Payment"}
                    </p>
                  </div>

                  {/* Items */}
                  <div className="bg-white rounded-xl border border-sand/50 p-5">
                    <h3 className="text-sm font-medium text-charcoal mb-3">
                      Order Items
                    </h3>
                    <div className="space-y-3">
                      {cartLines.length > 0 ? cartLines.map((line) => (
                        <div
                          key={line.lineId}
                          className="flex items-center justify-between py-2 border-b border-sand/50 last:border-0"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className="w-10 h-12 rounded-lg flex-shrink-0"
                              style={{
                                backgroundColor: line.variant?.colorHex || "#D4C5B9",
                              }}
                            />
                            <div>
                              <p className="text-sm font-medium text-charcoal">
                                {line.product?.title}
                              </p>
                              <p className="text-xs text-charcoal/75">
                                {line.variant?.name} × {line.quantity}
                              </p>
                            </div>
                          </div>
                          <p className="text-sm font-medium text-charcoal">
                            {fmtPrice(line.lineTotal)}
                          </p>
                        </div>
                      )) : quote?.items.map((line, index) => (
                        <div key={`${line.product_title}-${index}`} className="flex justify-between gap-4 border-b border-sand/50 py-2 text-sm last:border-0">
                          <span>{line.product_title} · {line.variant_name} × {line.quantity}</span>
                          <span>{fmtPrice(line.line_total_minor / 100)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {mode === "live" && quote && <details className="rounded-xl border border-sand bg-white p-4 text-sm text-charcoal/75" open>
                  <summary className="cursor-pointer font-medium text-charcoal">Checkout, shipping, and returns terms</summary>
                  <div className="mt-4 space-y-5">{Object.entries(quote.policies).map(([type, policy]) => <section key={type} aria-label={`${type.replaceAll("_", " ")} policy`}>
                    <h4 className="font-medium capitalize text-charcoal">{type.replaceAll("_", " ")} · version {policy.version}</h4>
                    <dl className="mt-2 space-y-3">{Object.entries(policy.content).map(([key, value]) => <div key={key}><dt className="font-medium capitalize">{key.replaceAll("_", " ")}</dt><dd className="mt-1 whitespace-pre-wrap">{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl>
                  </section>)}</div>
                </details>}
                {mode === "live" && <label className="flex items-start gap-3 rounded-xl border border-sand bg-white p-4 text-sm text-charcoal/75">
                  <input type="checkbox" checked={acceptedPolicy} onChange={(event) => setAcceptedPolicy(event.target.checked)} className="mt-1" />
                  <span>I agree to the checkout, shipping, and returns policies shown above for this order.</span>
                </label>}

                <div className="flex justify-between pt-4">
                  <button
                    onClick={() => setStep("payment")}
                    className="inline-flex items-center gap-1 text-sm text-charcoal/75 hover:text-terracotta transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Payment
                  </button>
                  <Button variant="primary" size="lg" disabled={mode !== "live" || !quote || !acceptedPolicy || submitting} onClick={() => void placeOrder()}>
                    {mode === "live" ? submitting ? "Placing order…" : "Place COD Order" : "Ordering unavailable"}
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Order Summary Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl border border-sand/50 p-6 sticky top-24 space-y-4">
              <h3 className="font-medium text-charcoal">Order Summary</h3>

              <div className="space-y-2">
                {cartLines.map((line) => (
                  <div
                    key={line.lineId}
                    className="flex justify-between text-sm"
                  >
                    <span className="text-charcoal/75 truncate max-w-[180px]">
                      {line.product?.title} × {line.quantity}
                    </span>
                    <span className="text-charcoal/70">
                      {fmtPrice(line.lineTotal)}
                    </span>
                  </div>
                ))}
                {cartLines.length === 0 && quote?.items.map((line, index) => (
                  <div key={`${line.product_title}-${index}`} className="flex justify-between text-sm">
                    <span className="text-charcoal/75 truncate max-w-[180px]">{line.product_title} × {line.quantity}</span>
                    <span className="text-charcoal/70">{fmtPrice(line.line_total_minor / 100)}</span>
                  </div>
                ))}
              </div>

              <div className="border-t border-sand/50 pt-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-charcoal/75">Subtotal</span>
                  <span className="text-charcoal">{fmtPrice(mode === "live" && quote ? quote.subtotal_minor / 100 : subtotal)}</span>
                </div>
                {mode === "live" && quote && quote.discount_minor > 0 && <div className="flex justify-between text-sm text-terracotta">
                  <span>Promotion{quote.applied_coupon ? ` · ${quote.applied_coupon.code}` : ""}</span>
                  <span>−{fmtPrice(quote.discount_minor / 100)}</span>
                </div>}
                <div className="flex justify-between text-sm">
                  <span className="text-charcoal/75">Shipping</span>
                  <span className="text-charcoal">
                    {mode === "live" && !quote ? "Calculated at review" : (mode === "live" ? quote!.shipping_charge_minor : shippingCost) === 0 ? "Free" : fmtPrice(mode === "live" ? quote!.shipping_charge_minor / 100 : shippingCost)}
                  </span>
                </div>
                <div className="border-t border-sand/50 pt-2 flex justify-between">
                  <span className="font-medium text-charcoal">Total</span>
                  <span className="font-medium text-charcoal">
                    {mode === "live" && !quote ? "Calculated at review" : fmtPrice(total)}
                  </span>
                </div>
              </div>

              <div className="pt-2 space-y-2">
                <div className="flex items-center gap-2 text-xs text-charcoal/75">
                  <ShieldCheck className="w-3.5 h-3.5 text-terracotta/60" />
                  {mode === "live" ? "Secure COD checkout" : "Checkout preview"}
                </div>
                <div className="flex items-center gap-2 text-xs text-charcoal/75">
                  <Truck className="w-3.5 h-3.5 text-terracotta/60" />
                  {formData.fulfillmentMethod === "delivery"
                    ? mode === "live" ? "Delivery fee shown in final quote" : "Delivery terms to be confirmed"
                    : mode === "live" ? "Pickup fee shown in final quote" : "Pickup details to be confirmed"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
