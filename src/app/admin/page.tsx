"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { jsonBody, staffJson, type StaffIdentity, type StaffMember } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

const ROLES = ["owner", "order_manager", "warehouse", "customer_support", "marketing"];
const ORDER_STATES = ["PENDING_CONFIRMATION", "CONFIRMED", "PROCESSING", "FULFILLED", "COMPLETED", "CANCELLED"] as const;
type DashboardSnapshot = {
  as_of: string;
  order_states: Record<(typeof ORDER_STATES)[number], number>;
  queues: {
    cod_confirmation?: number;
    packing?: number;
    stock_reservation_exceptions?: number;
    product_reviews?: number;
    zero_available_inventory?: number;
    low_stock_inventory?: number;
  };
};

export default function AdminHome() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [members, setMembers] = useState<StaffMember[]>([]);
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("order_manager");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const user = await staffJson<StaffIdentity>("auth/me");
      setIdentity(user);
      if (!user.totp_enabled && user.permission_keys.length === 0) {
        router.replace("/admin/enroll");
        return;
      }
      if (user.permission_keys.includes("dashboard.read")) {
        try {
          setDashboard(await staffJson<DashboardSnapshot>("admin/analytics/dashboard"));
          setDashboardError(null);
        } catch (cause) {
          setDashboardError(cause instanceof Error ? cause.message : "Operations snapshot could not be loaded.");
        }
      } else setDashboard(null);
      if (user.permission_keys.includes("staff.manage")) {
        setMembers(await staffJson<StaffMember[]>("admin/staff"));
      } else setMembers([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Staff session could not be loaded.");
      if (isUnauthorizedStaffError(cause)) {
        setIdentity(null); setMembers([]);
        router.replace("/admin/login");
      }
    } finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function logout() {
    setBusy(true);
    try { await staffJson<void>("auth/logout", { method: "POST" }); }
    finally { setIdentity(null); setMembers([]); router.replace("/admin/login"); setBusy(false); }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<void>("admin/staff/invitations", jsonBody({ email: inviteEmail, roles: [inviteRole] }));
      setNotice("Invitation queued for delivery."); setInviteEmail("");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Invitation failed."); }
    finally { setBusy(false); }
  }

  async function changeMember(path: string, body?: object) {
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson(path, body
        ? { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
        : { method: "POST" });
      setNotice("Staff access updated."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Staff access could not be updated."); await load(); }
    finally { setBusy(false); }
  }

  if (loading && !identity) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;

  return <div className="space-y-8">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Welcome, {identity.name}</h1><p className="mt-1 text-sm text-charcoal/75">{identity.email}</p></div>
      <div className="flex gap-3"><Link href="/admin/enroll" className="rounded-lg border border-sand px-4 py-2 text-sm">Authenticator</Link><button onClick={() => void logout()} disabled={busy} className="rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-50">Sign out</button></div>
    </div>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    {identity.permission_keys.includes("dashboard.read") && <section className="space-y-4 rounded-2xl border border-sand bg-white p-6">
      <div><h2 className="heading-sm">Current order-state snapshot</h2><p className="mt-1 text-sm text-charcoal/75">Counts reflect the current state of all orders, not a date-range sales report.{dashboard?.as_of && ` As of ${new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" }).format(new Date(dashboard.as_of))} PKT.`}</p></div>
      {dashboardError && <p role="alert" className="text-sm text-rust">{dashboardError}</p>}
      {dashboard ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{ORDER_STATES.map((state) => <div key={state} className="rounded-xl border border-sand/70 p-4">
        <p className="text-xs uppercase tracking-wide text-charcoal/75">{state.replaceAll("_", " ")}</p><p className="mt-1 text-2xl font-medium">{dashboard.order_states[state]}</p>
        {identity.permission_keys.includes("order.read") && <Link className="mt-2 inline-block text-sm text-terracotta underline" href={`/admin/orders?state=${state}`}>View orders</Link>}
      </div>)}</div> : !dashboardError ? <p role="status" className="text-sm text-charcoal/75">Loading order counts…</p> : null}
    </section>}
    {dashboard && Object.keys(dashboard.queues).length > 0 && <section className="space-y-4 rounded-2xl border border-sand bg-white p-6"><div><h2 className="heading-sm">Actionable queues</h2><p className="mt-1 text-sm text-charcoal/75">Current work counts; each link opens the queue staff can access.</p></div><div className="grid gap-3 sm:grid-cols-2">{dashboard.queues.cod_confirmation !== undefined && <Link href="/admin/orders/cod" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">COD awaiting confirmation</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.cod_confirmation}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open queue</span></Link>}{dashboard.queues.stock_reservation_exceptions !== undefined && <Link href="/admin/orders?work=stock-exceptions" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">Orders with stock reservation exceptions</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.stock_reservation_exceptions}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open stock exception queue</span></Link>}{dashboard.queues.packing !== undefined && <Link href="/admin/orders?work=packing" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">Delivery orders ready for packing</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.packing}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open packing queue</span></Link>}{dashboard.queues.product_reviews !== undefined && <Link href="/admin/reviews" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">Reviews awaiting moderation</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.product_reviews}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open queue</span></Link>}{dashboard.queues.low_stock_inventory !== undefined && <Link href="/admin/inventory?availability=low" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">Below configured stock threshold</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.low_stock_inventory}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open low-stock queue</span></Link>}{dashboard.queues.zero_available_inventory !== undefined && <Link href="/admin/inventory?availability=zero" className="rounded-xl border border-sand/70 p-4 hover:border-terracotta"><p className="text-xs uppercase tracking-wide text-charcoal/75">Balances with no available units</p><p className="mt-1 text-2xl font-medium">{dashboard.queues.zero_available_inventory}</p><span className="mt-2 inline-block text-sm text-terracotta underline">Open inventory queue</span></Link>}</div></section>}
    {identity.permission_keys.includes("order.read") && <Link href="/admin/orders/cod" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">COD confirmation queue →</h2><p className="mt-1 text-sm text-charcoal/75">Review buyers and record confirmation decisions.</p></Link>}
    {identity.permission_keys.includes("order.read") && <Link href="/admin/orders" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Order history →</h2><p className="mt-1 text-sm text-charcoal/75">Search orders and inspect accepted items, payment, fulfillment, and events.</p></Link>}
    {identity.permission_keys.includes("order.create_manual") && <Link href="/admin/orders/new" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Record a manual order →</h2><p className="mt-1 text-sm text-charcoal/75">Capture an order from a social or assisted sales channel.</p></Link>}
    {identity.permission_keys.includes("customer.read") && <Link href="/admin/customers" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Customer profiles →</h2><p className="mt-1 text-sm text-charcoal/75">Find profiles and review linked order history.</p></Link>}
    {identity.permission_keys.includes("review.moderate") && <Link href="/admin/reviews" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Product reviews →</h2><p className="mt-1 text-sm text-charcoal/75">Approve or reject purchase reviews before they appear publicly.</p></Link>}
    {identity.permission_keys.includes("notification.read") && <Link href="/admin/notifications" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Email delivery →</h2><p className="mt-1 text-sm text-charcoal/75">Inspect queued, retrying, sent, and failed system email statuses.</p></Link>}
    {identity.permission_keys.includes("catalog.read") && <Link href="/admin/catalog" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Catalog →</h2><p className="mt-1 text-sm text-charcoal/75">Review products, descriptions, publication state, and variant prices.</p></Link>}
    {identity.permission_keys.includes("inventory.read") && <Link href="/admin/inventory" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Inventory →</h2><p className="mt-1 text-sm text-charcoal/75">Inspect stock by SKU and location, receive units, and record count adjustments.</p></Link>}
    {identity.permission_keys.includes("analytics.read") && <Link href="/admin/analytics/attribution" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Creator attribution →</h2><p className="mt-1 text-sm text-charcoal/75">Review accepted order intake by creator, campaign, and sales source.</p></Link>}
    {identity.permission_keys.includes("settings.manage") && <Link href="/admin/settings" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Store settings and policies →</h2><p className="mt-1 text-sm text-charcoal/75">Manage versioned fulfillment rules and publish approved policy versions.</p></Link>}
    {identity.permission_keys.includes("promotion.read") && <Link href="/admin/promotions" className="block rounded-2xl border border-sand bg-white p-6 hover:border-terracotta"><h2 className="font-medium">Promotions →</h2><p className="mt-1 text-sm text-charcoal/75">Review and manage dated coupon codes with spend, redemption, and catalog limits.</p></Link>}
    {!identity.permission_keys.includes("staff.manage") && <div className="rounded-2xl border border-sand bg-white p-6"><h2 className="font-medium">Your access</h2><p className="mt-2 text-sm text-charcoal/75">Available capabilities: {identity.permission_keys.join(", ") || "none"}. Your workspace is limited to the capabilities assigned to your staff roles.</p></div>}
    {identity.permission_keys.includes("staff.manage") && <>
      <section className="rounded-2xl border border-sand bg-white p-6"><h2 className="heading-sm mb-4">Invite staff</h2><form onSubmit={(event) => void invite(event)} className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 flex-1 text-sm font-medium">Email<input required type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Role<select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3">{ROLES.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</select></label>
        <button disabled={busy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">Send invitation</button>
      </form></section>
      <section className="rounded-2xl border border-sand bg-white p-6"><h2 className="heading-sm mb-4">Staff members</h2><div className="space-y-4">{members.map((member) => <MemberCard key={`${member.id}:${member.updated_at}`} member={member} busy={busy} onChange={changeMember} />)}</div></section>
    </>}
  </div>;
}

function MemberCard({ member, busy, onChange }: {
  member: StaffMember;
  busy: boolean;
  onChange: (path: string, body?: object) => Promise<void>;
}) {
  const [roles, setRoles] = useState(member.roles);
  const toggle = (role: string) => setRoles((current) => current.includes(role) ? current.filter((entry) => entry !== role) : [...current, role]);
  return <div className="rounded-xl border border-sand/70 p-4">
    <div className="flex flex-wrap justify-between gap-3"><div><p className="font-medium">{member.display_name || member.email}</p><p className="text-sm text-charcoal/75">{member.email} · {member.status.toLowerCase()} · {member.totp_enabled ? "authenticator enabled" : "authenticator pending"}</p></div>
      <button disabled={busy} onClick={() => void onChange(`admin/staff/${member.id}/${member.status === "SUSPENDED" ? "activate" : "suspend"}`)} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">{member.status === "SUSPENDED" ? "Activate" : "Suspend"}</button></div>
    <fieldset className="mt-4"><legend className="mb-2 text-sm font-medium">Roles</legend><div className="flex flex-wrap gap-3">{ROLES.map((role) => <label key={role} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={roles.includes(role)} onChange={() => toggle(role)} />{role.replaceAll("_", " ")}</label>)}</div></fieldset>
    <button disabled={busy || roles.length === 0 || [...roles].sort().join() === [...member.roles].sort().join()} onClick={() => void onChange(`admin/staff/${member.id}/roles`, { role_keys: roles, expected_updated_at: member.updated_at })} className="mt-4 rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-40">Save roles</button>
  </div>;
}
