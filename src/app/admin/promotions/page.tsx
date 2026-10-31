"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type CouponType = "PERCENT" | "FIXED";
interface Coupon { id: string; code: string; type: CouponType; value_minor: number; state: string; is_active: boolean; min_order_minor: number | null; max_discount_minor: number | null; usage_limit: number | null; per_customer_limit: number | null; starts_at: string | null; ends_at: string | null; product_ids: string[]; category_ids: string[] }
interface CatalogProduct { id: string; title: string; slug: string; status: string }
interface CatalogCategory { id: string; name: string; children?: CatalogCategory[] }
interface ProductList { items: CatalogProduct[]; next_cursor: string | null }
interface CategoryList { items: CatalogCategory[] }

function flattenCategories(categories: CatalogCategory[]): CatalogCategory[] {
  return categories.flatMap((category) => [category, ...flattenCategories(category.children ?? [])]);
}

function localDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export default function PromotionsPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Coupon | null>(null);
  const [savedAction, setSavedAction] = useState<"created" | "updated">("created");
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [productsCursor, setProductsCursor] = useState<string | null>(null);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [editing, setEditing] = useState<Coupon | null>(null);
  const [code, setCode] = useState("");
  const [type, setType] = useState<CouponType>("PERCENT");
  const [value, setValue] = useState("");
  const [minimum, setMinimum] = useState("");
  const [cap, setCap] = useState("");
  const [usageLimit, setUsageLimit] = useState("");
  const [customerLimit, setCustomerLimit] = useState("1");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [productIds, setProductIds] = useState<string[]>([]);
  const [categoryIds, setCategoryIds] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      staffJson<StaffIdentity>("auth/me").then((user) => {
        if (active) setIdentity(user);
      }).catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      }).finally(() => {
        if (active) setLoading(false);
      });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  useEffect(() => {
    if (!identity?.permission_keys.includes("promotion.read")) return;
    let active = true;
    const canWrite = identity.permission_keys.includes("promotion.write");
    const catalogRequests = canWrite
      ? Promise.all([
          staffJson<ProductList>("admin/catalog/products?limit=100&status=PUBLISHED"),
          staffJson<CategoryList>("admin/catalog/categories"),
        ])
      : Promise.resolve(null);
    Promise.all([staffJson<Coupon[]>("admin/coupons"), catalogRequests]).then(([promotionList, catalog]) => {
      if (!active) return;
      setCoupons(promotionList);
      if (catalog) {
        const [productList, categoryList] = catalog;
        setProducts(productList.items);
        setProductsCursor(productList.next_cursor);
        setCategories(flattenCategories(categoryList.items));
      }
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Promotion data could not be loaded.");
    });
    return () => { active = false; };
  }, [identity]);

  async function loadMoreProducts() {
    if (!productsCursor || loadingProducts) return;
    setLoadingProducts(true); setError(null);
    try {
      const page = await staffJson<ProductList>(
        `admin/catalog/products?limit=100&status=PUBLISHED&after=${encodeURIComponent(productsCursor)}`,
      );
      setProducts((current) => [...current, ...page.items]);
      setProductsCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "More products could not be loaded.");
    } finally { setLoadingProducts(false); }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setCreated(null);
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0 || (type === "PERCENT" && numericValue > 100)) {
      setError(type === "PERCENT" ? "Enter a percentage from 1 to 100." : "Enter a positive amount.");
      setBusy(false); return;
    }
    const body = {
      code: code.trim().toUpperCase(), type,
      value_minor: type === "PERCENT" ? Math.round(numericValue) : Math.round(numericValue * 100),
      min_order_minor: minimum ? Math.round(Number(minimum) * 100) : null,
      max_discount_minor: type === "PERCENT" && cap ? Math.round(Number(cap) * 100) : null,
      usage_limit: usageLimit ? Number(usageLimit) : null,
      per_customer_limit: customerLimit ? Number(customerLimit) : null,
      starts_at: startsAt ? new Date(startsAt).toISOString() : null,
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      product_ids: productIds, category_ids: categoryIds,
      is_active: editing?.is_active ?? true,
    };
    try {
      const result = editing
        ? await staffJson<Coupon>(`admin/coupons/${editing.id}`, { ...jsonBody(body), method: "PATCH" })
        : await staffJson<Coupon>("admin/coupons", jsonBody(body));
      setCreated(result);
      setSavedAction(editing ? "updated" : "created");
      setCoupons((current) => [result, ...current.filter((coupon) => coupon.id !== result.id)]);
      resetForm();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Promotion could not be created.");
    } finally { setBusy(false); }
  }

  function resetForm() {
    setEditing(null); setCode(""); setType("PERCENT"); setValue(""); setMinimum("");
    setCap(""); setUsageLimit(""); setCustomerLimit("1"); setStartsAt("");
    setEndsAt(""); setProductIds([]); setCategoryIds([]);
  }

  function editCoupon(coupon: Coupon) {
    setEditing(coupon); setCreated(null); setCode(coupon.code); setType(coupon.type);
    setValue(coupon.type === "PERCENT" ? String(coupon.value_minor) : String(coupon.value_minor / 100));
    setMinimum(coupon.min_order_minor === null ? "" : String(coupon.min_order_minor / 100));
    setCap(coupon.max_discount_minor === null ? "" : String(coupon.max_discount_minor / 100));
    setUsageLimit(coupon.usage_limit === null ? "" : String(coupon.usage_limit));
    setCustomerLimit(coupon.per_customer_limit === null ? "" : String(coupon.per_customer_limit));
    setStartsAt(localDate(coupon.starts_at)); setEndsAt(localDate(coupon.ends_at));
    setProductIds(coupon.product_ids); setCategoryIds(coupon.category_ids);
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("promotion.read")) return <p role="alert">Promotion access is not included in your staff permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;
  const canWrite = identity.permission_keys.includes("promotion.write");

  return <div className="mx-auto max-w-4xl space-y-8">
    <header><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Promotions</h1><p className="mt-2 text-sm text-charcoal/75">Codes are checked against the live cart and reserved when an order is accepted. Choose eligible catalog items or leave both scopes empty to include all products.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {created && <p role="status" className="rounded-lg bg-warm-cream p-4">Promotion <strong>{created.code}</strong> {savedAction}.</p>}
    <section className="space-y-3"><h2 className="heading-sm">Existing codes</h2>{coupons.length ? <div className="grid gap-3 md:grid-cols-2">{coupons.map((coupon) => <article key={coupon.id} className="rounded-xl border border-sand bg-white p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{coupon.code}</h3><p className="mt-1 text-sm text-charcoal/75">{coupon.type === "PERCENT" ? `${coupon.value_minor}% off` : `PKR ${(coupon.value_minor / 100).toFixed(2)} off`} · {coupon.is_active ? "Active" : "Paused"}</p><p className="text-xs text-charcoal/75">{coupon.product_ids.length + coupon.category_ids.length ? `${coupon.product_ids.length + coupon.category_ids.length} catalog scopes` : "All products"}</p></div>{canWrite && <button type="button" disabled={busy} onClick={() => editCoupon(coupon)} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Edit</button>}</div></article>)}</div> : <p className="text-sm text-charcoal/75">No promotions have been created yet.</p>}</section>
    {canWrite ? <form onSubmit={(event) => void create(event)}><fieldset disabled={busy} className="space-y-6 rounded-2xl border border-sand bg-white p-6">
      <h2 className="heading-sm">{editing ? `Edit ${editing.code}` : "Create a promotion"}</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Code<input required minLength={1} maxLength={100} value={code} onChange={(event) => setCode(event.target.value)} placeholder="WELCOME10" className="mt-1 block w-full rounded-lg border border-sand p-3 uppercase" /></label>
        <label className="text-sm font-medium">Discount type<select value={type} onChange={(event) => setType(event.target.value as CouponType)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="PERCENT">Percentage</option><option value="FIXED">Fixed amount (PKR)</option></select></label>
        <label className="text-sm font-medium">{type === "PERCENT" ? "Discount percent" : "Discount amount (PKR)"}<input required type="number" min={type === "PERCENT" ? 1 : 0.01} max={type === "PERCENT" ? 100 : undefined} step={type === "PERCENT" ? 1 : "0.01"} value={value} onChange={(event) => setValue(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Minimum cart value (PKR)<input type="number" min="0" step="0.01" value={minimum} onChange={(event) => setMinimum(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        {type === "PERCENT" && <label className="text-sm font-medium">Maximum discount (PKR)<input type="number" min="0.01" step="0.01" value={cap} onChange={(event) => setCap(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>}
        <label className="text-sm font-medium">Total uses<input type="number" min="1" step="1" value={usageLimit} onChange={(event) => setUsageLimit(event.target.value)} placeholder="No limit" className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Uses per customer<input type="number" min="1" step="1" value={customerLimit} onChange={(event) => setCustomerLimit(event.target.value)} placeholder="No limit" className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Starts at<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="text-sm font-medium">Ends at<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      </div>
      <fieldset><legend className="text-sm font-medium">Eligible products <span className="font-normal text-charcoal/75">(none selected means all products)</span></legend><div className="mt-2 grid max-h-48 gap-2 overflow-auto rounded-lg border border-sand p-3 sm:grid-cols-2">{products.map((product) => <label key={product.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={productIds.includes(product.id)} onChange={(event) => setProductIds((ids) => event.target.checked ? [...ids, product.id] : ids.filter((id) => id !== product.id))} />{product.title}</label>)}{products.length === 0 && <span className="text-sm text-charcoal/75">No published products found.</span>}</div>{productsCursor && <button type="button" disabled={busy || loadingProducts} onClick={() => void loadMoreProducts()} className="mt-2 rounded-lg border border-sand px-4 py-2 text-sm disabled:opacity-50">{loadingProducts ? "Loading products…" : "Load more products"}</button>}</fieldset>
      <fieldset><legend className="text-sm font-medium">Eligible categories <span className="font-normal text-charcoal/75">(none selected means all categories)</span></legend><div className="mt-2 grid max-h-48 gap-2 overflow-auto rounded-lg border border-sand p-3 sm:grid-cols-2">{categories.map((category) => <label key={category.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={categoryIds.includes(category.id)} onChange={(event) => setCategoryIds((ids) => event.target.checked ? [...ids, category.id] : ids.filter((id) => id !== category.id))} />{category.name}</label>)}{categories.length === 0 && <span className="text-sm text-charcoal/75">No categories found.</span>}</div></fieldset>
      {editing && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={editing.is_active} onChange={(event) => setEditing({ ...editing, is_active: event.target.checked })} />Promotion active</label>}
      <div className="flex gap-3"><button disabled={busy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Saving…" : editing ? "Save promotion" : "Create promotion"}</button>{editing && <button type="button" onClick={resetForm} className="rounded-lg border border-sand px-5 py-3 text-sm">Cancel edit</button>}</div>
    </fieldset></form> : <p className="rounded-lg bg-warm-cream p-4 text-sm">You have read-only access to promotions.</p>}
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}
