"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

interface Identity { customer_id: string; email: string }
interface AccountOrder { order_id: string; order_number: string; state: string; total_minor: number; created_at: string; events: Array<{ label: string; occurred_at: string }> }
interface MarketingConsent { consented: boolean; recorded_at: string | null }

export default function AccountPage() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [orders, setOrders] = useState<AccountOrder[]>([]);
  const [marketingConsent, setMarketingConsent] = useState<MarketingConsent | null>(null);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeRequested, setCodeRequested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadAccount = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const me = await fetch("/api/customer/me", { cache: "no-store" });
      if (me.status === 401) {
        setIdentity(null);
        setOrders([]);
        setMarketingConsent(null);
        return;
      }
      if (!me.ok) throw new Error("Account information is temporarily unavailable. Please retry.");

      const person = await me.json() as Identity;
      setIdentity(person);
      const [history, consent] = await Promise.all([
        fetch("/api/customer/orders", { cache: "no-store" }),
        fetch("/api/customer/consents/marketing-email", { cache: "no-store" }),
      ]);
      if (!history.ok || !consent.ok) {
        throw new Error("Account information is temporarily unavailable. Please retry.");
      }
      setOrders((await history.json() as { items: AccountOrder[] }).items);
      setMarketingConsent(await consent.json() as MarketingConsent);
    } catch {
      setLoadError("Account information is temporarily unavailable. Please retry.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { queueMicrotask(() => { void loadAccount(); }); }, [loadAccount]);

  async function post(path: string, payload: object = {}) {
    const response = await fetch(`/api/customer/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? "Please try again.");
    return result;
  }

  async function requestCode(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try { const result = await post("request-otp", { email }); setCodeRequested(true); setMessage(result.message); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  async function verifyCode(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try { await post("verify-otp", { email, code }); await loadAccount(); setCode(""); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  async function sessionAction(path: string) {
    setBusy(true); setMessage("");
    try { await post(path); if (path === "logout") { setIdentity(null); setOrders([]); setMarketingConsent(null); setCodeRequested(false); } else setMessage("Other sessions have been signed out."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  async function withdrawMarketingConsent() {
    setBusy(true); setMessage("");
    try {
      const result = await post("consents/marketing-email") as MarketingConsent;
      setMarketingConsent(result);
      setMessage("You are unsubscribed from optional marketing emails.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  return <div className="min-h-[60vh] bg-cream"><div className="container-page max-w-2xl py-16">
    <h1 className="heading-lg text-charcoal">Your account</h1>
    <p className="mt-3 text-charcoal/75">Sign in with a code sent to your email. Orders can be discussed with us on WhatsApp.</p>
    {loading ? <p className="mt-8" role="status">Loading account…</p> : loadError ? <div className="mt-8 rounded-2xl border border-sand bg-white p-6">
      <p role="alert" className="text-sm text-charcoal/75">{loadError}</p>
      <button type="button" onClick={() => void loadAccount()} className="mt-4 rounded-full bg-charcoal px-5 py-2 text-sm text-white">Retry account</button>
    </div> : identity ? <>
      <div className="mt-8 rounded-2xl border border-sand bg-white p-6">
        <p className="font-medium text-charcoal">{identity.email}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button disabled={busy} onClick={() => void sessionAction("logout")} className="rounded-full bg-charcoal px-5 py-2 text-sm text-white disabled:opacity-50">Sign out</button>
          <button disabled={busy} onClick={() => void sessionAction("logout-others")} className="rounded-full border border-sand px-5 py-2 text-sm text-charcoal disabled:opacity-50">Sign out other devices</button>
        </div>
      </div>
      <section className="mt-8 rounded-2xl border border-sand bg-white p-6">
        <h2 className="font-medium text-charcoal">Marketing email preference</h2>
        {marketingConsent?.consented ? <><p className="mt-2 text-sm text-charcoal/75">Optional marketing email consent is active.</p><button type="button" disabled={busy} onClick={() => void withdrawMarketingConsent()} className="mt-4 rounded-full border border-sand px-5 py-2 text-sm text-charcoal disabled:opacity-50">Unsubscribe from marketing emails</button></> : <p className="mt-2 text-sm text-charcoal/75">No optional marketing email consent is active. This preference does not change order-related communication.</p>}
      </section>
      <h2 className="mt-10 text-xl font-medium text-charcoal">Order history</h2>
      {orders.length ? <ul className="mt-4 space-y-3">{orders.map((order) => <li key={order.order_id} className="rounded-2xl border border-sand bg-white p-5">
        <p className="font-medium">{order.order_number}</p><p className="mt-1 text-sm text-charcoal/75">{order.state.replaceAll("_", " ").toLowerCase()} · PKR {(order.total_minor / 100).toFixed(2)} · {new Date(order.created_at).toLocaleDateString()}</p>
        {order.events.length > 0 && <details className="mt-3 border-t border-sand/60 pt-3"><summary className="cursor-pointer text-sm text-terracotta">Order progress</summary><ol className="mt-3 space-y-3">{order.events.map((event, index) => <li key={`${event.occurred_at}:${index}`} className="flex gap-3 text-sm"><span aria-hidden="true" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-terracotta" /><div><p>{event.label}</p><time dateTime={event.occurred_at} className="text-xs text-charcoal/75">{new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" }).format(new Date(event.occurred_at))} PKT</time></div></li>)}</ol></details>}
      </li>)}</ul> : <p className="mt-4 text-charcoal/75">No linked orders yet. An order placed while signed in appears here. You can also claim a guest order from its confirmation page in the same browser.</p>}
    </> : <div className="mt-8 rounded-2xl border border-sand bg-white p-6">
      <form onSubmit={requestCode} className="space-y-4">
        <label className="block text-sm font-medium" htmlFor="account-email">Email address</label>
        <input id="account-email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-lg border border-sand p-3" />
        <button disabled={busy} className="rounded-full bg-charcoal px-6 py-3 text-sm text-white disabled:opacity-50">{codeRequested ? "Send a new code" : "Email me a code"}</button>
      </form>
      {codeRequested && <form onSubmit={verifyCode} className="mt-6 space-y-4">
        <label className="block text-sm font-medium" htmlFor="account-code">Six-digit code</label>
        <input id="account-code" inputMode="numeric" pattern="[0-9]{6}" required autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value)} className="w-full rounded-lg border border-sand p-3" />
        <button disabled={busy} className="rounded-full bg-terracotta px-6 py-3 text-sm text-white disabled:opacity-50">Sign in</button>
      </form>}
    </div>}
    {message && <p role="status" className="mt-5 text-sm text-charcoal/75">{message}</p>}
    <Link href="/shop" className="mt-8 inline-block text-sm text-terracotta underline">Continue shopping</Link>
  </div></div>;
}
