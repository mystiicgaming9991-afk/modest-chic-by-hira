"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

interface CustomerProfile {
  id: string;
  normalized_phone: string | null;
  display_phone: string | null;
  name: string | null;
  email: string | null;
  account_status: "ACTIVE" | "SUSPENDED" | null;
  account_email: string | null;
  account_updated_at: string | null;
}

interface CustomerOrder {
  order_id: string;
  order_number: string;
  state: string;
  payment_method: string;
  payment_state: string;
  fulfillment_method: string;
  total_minor: number;
  created_at: string;
  events: Array<{
    event_type: string;
    previous_state: string | null;
    new_state: string | null;
    effective_at: string;
  }>;
}

interface CustomerAddress {
  id: string;
  recipient_name: string | null;
  phone: string | null;
  line1: string;
  line2: string | null;
  area: string | null;
  city: string;
  postal_code: string | null;
  delivery_notes: string | null;
  country_code: string;
  is_default: boolean;
  updated_at: string;
  default_address_updates?: Array<{ id: string; updated_at: string }>;
}

interface CustomerConsent {
  consented: boolean;
  source: string | null;
  recorded_at: string;
  policy_version_id: string | null;
}

export default function CustomersPage() {
  const router = useRouter();
  const profileLoadVersion = useRef(0);
  const searchVersion = useRef(0);
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [query, setQuery] = useState("");
  const [profiles, setProfiles] = useState<CustomerProfile[]>([]);
  const [selected, setSelected] = useState<CustomerProfile | null>(null);
  const [orders, setOrders] = useState<CustomerOrder[]>([]);
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [editingAddress, setEditingAddress] = useState<CustomerAddress | null>(null);
  const [marketingConsent, setMarketingConsent] = useState<CustomerConsent | null>(null);
  const [consentLoaded, setConsentLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [addressBusy, setAddressBusy] = useState(false);
  const [accountBusy, setAccountBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      staffJson<StaffIdentity>("auth/me")
        .then((user) => {
          if (!active) return;
          setIdentity(user);
          if (!user.permission_keys.includes("customer.read")) {
            setError("Customer access is not included in your staff permissions.");
          }
        })
        .catch((cause) => {
          if (!active) return;
          if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
          else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
        })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestVersion = ++searchVersion.current;
    profileLoadVersion.current += 1;
    setBusy(true); setError(null); setProfiles([]); setSelected(null); setOrders([]); setAddresses([]); setEditingAddress(null); setMarketingConsent(null); setConsentLoaded(false);
    try {
      const result = await staffJson<CustomerProfile[]>(`admin/customers?q=${encodeURIComponent(query.trim())}`);
      if (requestVersion !== searchVersion.current) return;
      setProfiles(result);
    } catch (cause) {
      if (requestVersion === searchVersion.current) setError(cause instanceof Error ? cause.message : "Customer search failed.");
    } finally {
      if (requestVersion === searchVersion.current) setBusy(false);
    }
  }

  async function openProfile(profile: CustomerProfile) {
    const requestVersion = ++profileLoadVersion.current;
    setBusy(true); setError(null); setSelected(profile);
    setOrders([]); setAddresses([]); setEditingAddress(null); setMarketingConsent(null); setConsentLoaded(false);
    try {
      const [history, savedAddresses, consent] = await Promise.all([
        staffJson<CustomerOrder[]>(`admin/customers/${profile.id}/orders`),
        staffJson<CustomerAddress[]>(`admin/customers/${profile.id}/addresses`),
        staffJson<CustomerConsent | null>(`admin/customers/${profile.id}/consents/marketing-email`),
      ]);
      if (requestVersion !== profileLoadVersion.current) return;
      setOrders(history);
      setAddresses(savedAddresses);
      setMarketingConsent(consent);
      setConsentLoaded(true);
    }
    catch (cause) {
      if (requestVersion === profileLoadVersion.current) {
        setError(cause instanceof Error ? cause.message : "Customer profile details could not be loaded.");
      }
    } finally {
      if (requestVersion === profileLoadVersion.current) setBusy(false);
    }
  }

  async function saveAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || addressBusy) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const optional = (key: string) => String(form.get(key) ?? "").trim() || null;
    setAddressBusy(true);
    setError(null);
    try {
      const values = {
        recipient_name: optional("recipient_name"),
        phone: optional("phone"),
        line1: String(form.get("line1") ?? "").trim(),
        line2: optional("line2"),
        area: optional("area"),
        city: String(form.get("city") ?? "").trim(),
        postal_code: optional("postal_code"),
        delivery_notes: optional("delivery_notes"),
        country_code: String(form.get("country_code") ?? "PK").trim().toUpperCase() || "PK",
        is_default: form.get("is_default") === "on",
      };
      const address = editingAddress
        ? await staffJson<CustomerAddress>(`admin/customers/${selected.id}/addresses/${editingAddress.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...values, expected_updated_at: editingAddress.updated_at }),
        })
        : await staffJson<CustomerAddress>(`admin/customers/${selected.id}/addresses`, jsonBody(values));
      setAddresses((current) => editingAddress
        ? current.map((existing) => existing.id === address.id
          ? address
          : address.is_default ? clearAddressDefault(existing, address.default_address_updates) : existing)
        : [address, ...current.map((existing) => address.is_default
          ? clearAddressDefault(existing, address.default_address_updates)
          : existing)]);
      setEditingAddress(null);
      formElement.reset();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Customer address could not be saved.");
    } finally {
      setAddressBusy(false);
    }
  }

  async function toggleAccountStatus() {
    if (!selected?.account_status || !selected.account_updated_at || accountBusy) return;
    const status = selected.account_status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
    setAccountBusy(true);
    setError(null);
    try {
      const result = await staffJson<{
        customer_id: string;
        status: "ACTIVE" | "SUSPENDED";
        updated_at: string;
      }>(`admin/customers/${selected.id}/account-status`, jsonBody({
        status,
        expected_updated_at: selected.account_updated_at,
      }));
      const updated = {
        ...selected,
        account_status: result.status,
        account_updated_at: result.updated_at,
      };
      setSelected(updated);
      setProfiles((current) => current.map((profile) => profile.id === updated.id ? updated : profile));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Customer account status could not be changed.");
    } finally {
      setAccountBusy(false);
    }
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("customer.read")) return <p role="alert">Customer access is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="space-y-8">
    <div><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Customer profiles</h1><p className="mt-1 text-sm text-charcoal/75">Search by name, email, or phone to review linked order history.</p></div>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    <form onSubmit={(event) => void search(event)} className="flex flex-wrap items-end gap-3 rounded-2xl border border-sand bg-white p-5">
      <label htmlFor="customer-query" className="min-w-56 flex-1 text-sm font-medium">Name, email, or phone<input id="customer-query" required minLength={2} maxLength={100} value={query} onChange={(event) => setQuery(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <button disabled={busy || addressBusy || accountBusy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">Search</button>
    </form>
    {profiles.length > 0 && <section className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3">{profiles.map((profile) => <button key={profile.id} disabled={addressBusy || accountBusy} onClick={() => void openProfile(profile)} className={`w-full rounded-2xl border bg-white p-5 text-left disabled:opacity-60 ${selected?.id === profile.id ? "border-terracotta" : "border-sand hover:border-terracotta/60"}`}>
        <span className="block font-medium">{profile.name || "Customer"}</span><span className="mt-1 block text-sm text-charcoal/75">{profile.display_phone || profile.normalized_phone || "No phone"}</span>{profile.account_email || profile.email ? <span className="block text-sm text-charcoal/75">{profile.account_email || profile.email}</span> : null}{profile.account_status && <span className={`mt-2 inline-block rounded-full px-2 py-1 text-xs ${profile.account_status === "ACTIVE" ? "bg-emerald-50 text-emerald-800" : "bg-rust/10 text-rust"}`}>Account {profile.account_status.toLowerCase()}</span>}
      </button>)}</div>
      <div className="rounded-2xl border border-sand bg-white p-5">
        <h2 className="font-medium">{selected ? `Orders for ${selected.name || selected.display_phone || "customer"}` : "Select a customer"}</h2>
        {selected?.account_status && identity.permission_keys.includes("customer.manage") && <div className="my-4 rounded-xl border border-sand p-4"><p className="text-sm text-charcoal/70">Verified email account: <strong>{selected.account_email || selected.email}</strong> · {selected.account_status.toLowerCase()}</p><p className="mt-1 text-xs text-charcoal/75">Suspending immediately revokes active customer sessions. Re-activation allows a fresh email code sign-in.</p><button type="button" disabled={accountBusy} onClick={() => void toggleAccountStatus()} className={`mt-3 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50 ${selected.account_status === "ACTIVE" ? "border border-rust/40 text-rust" : "bg-charcoal text-white"}`}>{accountBusy ? "Updating account…" : selected.account_status === "ACTIVE" ? "Suspend account" : "Re-activate account"}</button></div>}
        {selected && <section className="mt-5 border-t border-sand pt-4">
          <h3 className="font-medium">Saved addresses</h3>
          {busy ? <p role="status" className="mt-2 text-sm text-charcoal/75">Loading saved addresses…</p> : addresses.length ? <ul className="mt-3 space-y-3">{addresses.map((address) => <li key={address.id} className="rounded-xl bg-cream/70 p-3 text-sm">
            <p className="font-medium">{address.recipient_name || "Recipient not set"}{address.is_default && <span className="ml-2 rounded-full bg-white px-2 py-1 text-[10px] uppercase tracking-wide text-charcoal/75">Default</span>}</p>
            <p className="mt-1">{[address.line1, address.line2, address.area, address.city, address.postal_code, address.country_code].filter(Boolean).join(", ")}</p>
            {(address.phone || address.delivery_notes) && <p className="mt-1 text-xs text-charcoal/75">{[address.phone, address.delivery_notes].filter(Boolean).join(" · ")}</p>}
            {identity.permission_keys.includes("customer.manage") && <button type="button" onClick={() => setEditingAddress(address)} className="mt-2 text-xs font-medium text-terracotta underline">Edit address</button>}
          </li>)}</ul> : <p className="mt-2 text-sm text-charcoal/75">No saved addresses.</p>}
          {identity.permission_keys.includes("customer.manage") && <form key={editingAddress?.id ?? "new-address"} onSubmit={(event) => void saveAddress(event)} className="mt-4 space-y-3 rounded-xl border border-sand p-4">
            <h4 className="text-sm font-medium">{editingAddress ? "Edit saved address" : "Add a saved address"}</h4>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-medium">Recipient name<input name="recipient_name" defaultValue={editingAddress?.recipient_name ?? ""} maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">Recipient phone<input name="phone" defaultValue={editingAddress?.phone ?? ""} maxLength={30} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium sm:col-span-2">Address line 1<input name="line1" defaultValue={editingAddress?.line1 ?? ""} required maxLength={500} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">Address line 2<input name="line2" defaultValue={editingAddress?.line2 ?? ""} maxLength={500} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">Area<input name="area" defaultValue={editingAddress?.area ?? ""} maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">City<input name="city" defaultValue={editingAddress?.city ?? ""} required maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">Postal code<input name="postal_code" defaultValue={editingAddress?.postal_code ?? ""} maxLength={20} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
              <label className="text-xs font-medium">Country code<input name="country_code" defaultValue={editingAddress?.country_code ?? "PK"} required minLength={2} maxLength={2} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm uppercase" /></label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm"><input name="is_default" type="checkbox" defaultChecked={editingAddress?.is_default ?? false} />Set as default address</label>
              <label className="text-xs font-medium sm:col-span-2">Delivery notes<textarea name="delivery_notes" defaultValue={editingAddress?.delivery_notes ?? ""} rows={2} className="mt-1 block w-full rounded-lg border border-sand p-2.5 text-sm" /></label>
            </div>
            <div className="flex gap-3"><button type="submit" disabled={addressBusy} className="rounded-lg bg-charcoal px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{addressBusy ? "Saving address…" : editingAddress ? "Update address" : "Save address"}</button>{editingAddress && <button type="button" onClick={() => setEditingAddress(null)} className="rounded-lg border border-sand px-4 py-2 text-sm">Cancel</button>}</div>
          </form>}
        </section>}
        {selected && <section className="mt-5 border-t border-sand pt-4">
          <h3 className="font-medium">Marketing email preference</h3>
          {busy ? <p role="status" className="mt-2 text-sm text-charcoal/75">Loading current preference…</p>
            : !consentLoaded ? <p className="mt-2 text-sm text-charcoal/75">Current preference could not be loaded.</p>
              : marketingConsent === null ? <p className="mt-2 text-sm text-charcoal/75">No recorded marketing email preference.</p>
                : <p className="mt-2 text-sm text-charcoal/70">{marketingConsent.consented ? "Consent recorded" : "Opted out"} · {marketingConsent.source?.replaceAll("_", " ") || "source not recorded"} · {new Date(marketingConsent.recorded_at).toLocaleString()}</p>}
          <p className="mt-1 text-xs text-charcoal/75">This records the current preference only; marketing sends remain disabled until approved consent language and suppression rules are in place.</p>
        </section>}
        {!selected ? <p className="mt-2 text-sm text-charcoal/75">Order details are limited to the selected profile’s explicitly linked orders.</p> : busy ? <p role="status" className="mt-3 text-sm">Loading order history…</p> : orders.length ? <ul className="mt-4 space-y-4">{orders.map((order) => <li key={order.order_id} className="border-t border-sand pt-4">
          <div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{order.order_number}</span><span className="text-sm">PKR {(order.total_minor / 100).toFixed(2)}</span></div>
          <p className="mt-1 text-xs text-charcoal/75">{order.state.replaceAll("_", " ").toLowerCase()} · {order.payment_method} {order.payment_state.toLowerCase()} · {order.fulfillment_method.toLowerCase()} · {new Date(order.created_at).toLocaleDateString()}</p>
          <ol className="mt-3 space-y-1 text-xs text-charcoal/75">{order.events.map((entry, index) => <li key={`${entry.event_type}:${index}`}>{entry.event_type.replaceAll(".", " ")} · {new Date(entry.effective_at).toLocaleString()}</li>)}</ol>
        </li>)}</ul> : <p className="mt-3 text-sm text-charcoal/75">No linked orders. Contact matches are not used to claim guest orders.</p>}
      </div>
    </section>}
    {profiles.length === 0 && query && <p className="text-sm text-charcoal/75">No matching profiles. Search results are limited to 50 records.</p>}
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}

function clearAddressDefault(
  address: CustomerAddress,
  updates: CustomerAddress["default_address_updates"],
): CustomerAddress {
  const update = updates?.find((item) => item.id === address.id);
  return {
    ...address,
    is_default: false,
    ...(update ? { updated_at: update.updated_at } : {}),
  };
}
