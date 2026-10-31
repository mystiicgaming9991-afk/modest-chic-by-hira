"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type ProductStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
interface Product {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  fabric: string | null;
  care: string | null;
  dimensions: string | null;
  status: ProductStatus;
  created_at: string;
  updated_at: string;
}
interface Variant {
  id: string;
  product_id: string;
  sku: string;
  color_name: string;
  color_hex: string | null;
  dimensions: string | null;
  weight_grams: number | null;
  price_minor: number;
  sale_price_minor: number | null;
  currency: string;
  is_active: boolean;
  updated_at: string;
}
interface ProductMedia {
  id: string;
  object_key: string;
  media_type: string;
  alt_text: string | null;
  width: number | null;
  height: number | null;
  sort_order: number;
  is_primary: boolean;
  status: ProductStatus;
}
interface ProductDetail extends Product { variants: Variant[]; media: ProductMedia[] }
interface ProductPage { items: Product[]; next_cursor: string | null }
interface ProductForm {
  slug: string;
  title: string;
  description: string;
  fabric: string;
  care: string;
  dimensions: string;
  status: "DRAFT" | "PUBLISHED";
}
interface VariantForm { sku: string; color_name: string; color_hex: string; price_minor: string; sale_price_minor: string }

const emptyProduct: ProductForm = { slug: "", title: "", description: "", fabric: "", care: "", dimensions: "", status: "DRAFT" };
const emptyVariant: VariantForm = { sku: "", color_name: "", color_hex: "", price_minor: "", sale_price_minor: "" };
const money = (minor: number) => `PKR ${(minor / 100).toFixed(2)}`;

export default function CatalogAdminPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<ProductDetail | null>(null);
  const [productForm, setProductForm] = useState<ProductForm>(emptyProduct);
  const [variantForm, setVariantForm] = useState<VariantForm>(emptyVariant);
  const [statusFilter, setStatusFilter] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const productListRequest = useRef(0);
  const productDetailRequest = useRef(0);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<StaffIdentity>("auth/me").then((user) => {
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

  async function loadProducts(after?: string, append = false, filter = statusFilter) {
    const requestId = ++productListRequest.current;
    const detailRequestId = productDetailRequest.current;
    const selectedAtStart = selected;
    setBusy(true); setError(null);
    const params = new URLSearchParams({ limit: "50" });
    if (filter) params.set("status", filter);
    if (after) params.set("after", after);
    try {
      const page = await staffJson<ProductPage>(`admin/catalog/products?${params}`);
      if (requestId !== productListRequest.current) return;
      setProducts((current) => append ? [...current, ...page.items] : page.items);
      setNextCursor(page.next_cursor);
      if (!append && detailRequestId === productDetailRequest.current && selectedAtStart
        && !page.items.some((product) => product.id === selectedAtStart.id)) setSelected(null);
    } catch (cause) {
      if (requestId === productListRequest.current) {
        setError(cause instanceof Error ? cause.message : "Catalog could not be loaded.");
      }
    } finally {
      if (requestId === productListRequest.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!identity?.permission_keys.includes("catalog.read")) return;
    const timer = window.setTimeout(() => void loadProducts(), 0);
    return () => window.clearTimeout(timer);
    // Catalog loads once after the staff identity is known.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity]);

  async function openProduct(product: Product) {
    const requestId = ++productDetailRequest.current;
    setBusy(true); setError(null); setNotice(null); setSelected(null);
    try {
      const detail = await staffJson<ProductDetail>(`admin/catalog/products/${product.id}`);
      if (requestId !== productDetailRequest.current) return;
      setSelected(detail);
      setProductForm({
        slug: detail.slug,
        title: detail.title,
        description: detail.description ?? "",
        fabric: detail.fabric ?? "",
        care: detail.care ?? "",
        dimensions: detail.dimensions ?? "",
        status: detail.status === "PUBLISHED" ? "PUBLISHED" : "DRAFT",
      });
    } catch (cause) {
      if (requestId === productDetailRequest.current) {
        setError(cause instanceof Error ? cause.message : "Product details could not be loaded.");
      }
    } finally {
      if (requestId === productDetailRequest.current) setBusy(false);
    }
  }

  async function createProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    try {
      const product = await staffJson<Product>("admin/catalog/products", jsonBody(productPayload(productForm)));
      setStatusFilter("");
      await loadProducts(undefined, false, "");
      await openProduct(product);
      setNotice("Draft product created. Add its variants before publishing.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Product could not be created."); }
    finally { setBusy(false); }
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Product>(`admin/catalog/products/${selected.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(productPayload(productForm, selected.updated_at)),
      });
      await refreshSelected(selected.id);
      await loadProducts();
      setNotice("Product details saved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Product could not be saved."); }
    finally { setBusy(false); }
  }

  async function addVariant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Variant>(`admin/catalog/products/${selected.id}/variants`, jsonBody({
        sku: variantForm.sku.trim(),
        color_name: variantForm.color_name.trim(),
        color_hex: variantForm.color_hex || null,
        price_minor: parseInt(variantForm.price_minor, 10),
        sale_price_minor: variantForm.sale_price_minor ? parseInt(variantForm.sale_price_minor, 10) : null,
      }));
      setVariantForm(emptyVariant);
      await refreshSelected(selected.id);
      setNotice("Variant added.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Variant could not be added."); }
    finally { setBusy(false); }
  }

  async function attachMedia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || selected.status === "ARCHIVED") return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<ProductMedia>(`admin/catalog/products/${selected.id}/media`, jsonBody({
        object_key: String(values.get("object_key") ?? "").trim(),
        media_type: String(values.get("media_type") ?? "image/webp"),
        alt_text: String(values.get("alt_text") ?? "").trim() || null,
        width: String(values.get("width") ?? "").trim() ? Number(values.get("width")) : null,
        height: String(values.get("height") ?? "").trim() ? Number(values.get("height")) : null,
        sort_order: String(values.get("sort_order") ?? "0").trim() ? Number(values.get("sort_order")) : 0,
        is_primary: values.get("is_primary") === "on",
      }));
      form.reset();
      await refreshSelected(selected.id);
      setNotice("Media metadata attached. Published products expose this metadata through the public catalog; image delivery is limited to local assets until storage is configured.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Media metadata could not be attached."); }
    finally { setBusy(false); }
  }

  async function updateVariant(variant: Variant, changes: Partial<Variant>) {
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Variant>(`admin/catalog/variants/${variant.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...changes, expected_updated_at: variant.updated_at }),
      });
      if (selected) await refreshSelected(selected.id);
      setNotice(`Variant ${variant.sku} saved.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Variant could not be updated."); }
    finally { setBusy(false); }
  }

  async function archiveProduct() {
    if (!selected) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Product>(`admin/catalog/products/${selected.id}/archive`, { method: "POST" });
      setSelected(null);
      setNotice("Product archived. Existing order snapshots remain available.");
      await loadProducts();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Product could not be archived."); }
    finally { setBusy(false); }
  }

  async function refreshSelected(productId: string) {
    const detail = await staffJson<ProductDetail>(`admin/catalog/products/${productId}`);
    setSelected(detail);
    setProductForm({
      slug: detail.slug,
      title: detail.title,
      description: detail.description ?? "",
      fabric: detail.fabric ?? "",
      care: detail.care ?? "",
      dimensions: detail.dimensions ?? "",
      status: detail.status === "PUBLISHED" ? "PUBLISHED" : "DRAFT",
    });
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("catalog.read")) return <p role="alert">Catalog access is not included in your permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="space-y-8">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs uppercase tracking-widest text-terracotta">Staff workspace</p><h1 className="heading-md mt-2">Catalog</h1><p className="mt-2 text-sm text-charcoal/75">Manage product copy, publication state, variant pricing, and SKU details.</p></div>
      <div className="flex gap-4 text-sm"><Link href="/admin/catalog/groups" className="text-terracotta underline">Categories and collections</Link><Link href="/admin" className="text-terracotta underline">Back to staff home</Link></div>
    </header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(18rem,0.8fr)_minmax(32rem,1.4fr)]">
      <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
        <div className="flex items-center justify-between gap-3"><h2 className="font-medium">Products</h2><select aria-label="Filter products by status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); void loadProducts(undefined, false, event.target.value); }} className="rounded-lg border border-sand bg-white p-2 text-sm"><option value="">All statuses</option><option value="DRAFT">Draft</option><option value="PUBLISHED">Published</option><option value="ARCHIVED">Archived</option></select></div>
        <ul className="space-y-2">{products.map((product) => <li key={product.id}><button type="button" onClick={() => void openProduct(product)} className={`w-full rounded-xl border p-3 text-left ${selected?.id === product.id ? "border-terracotta" : "border-sand hover:border-terracotta/60"}`}><span className="flex items-center justify-between gap-3"><strong>{product.title}</strong><span className="text-xs">{product.status}</span></span><span className="mt-1 block text-xs text-charcoal/75">/{product.slug}</span></button></li>)}</ul>
        {nextCursor && <button type="button" disabled={busy} onClick={() => void loadProducts(nextCursor, true)} className="w-full rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Load more</button>}
        {!products.length && <p className="text-sm text-charcoal/75">{busy ? "Loading products…" : "No products in this view."}</p>}
      </section>
      <div className="space-y-5">
        {identity.permission_keys.includes("catalog.write") && !selected && <section className="rounded-2xl border border-sand bg-white p-5"><h2 className="heading-sm">Create product</h2><p className="mt-1 text-sm text-charcoal/75">New products start as drafts. Add variants, then publish when the content is approved.</p><ProductFormFields value={productForm} onChange={setProductForm} allowStatus={false} busy={busy} onSubmit={createProduct} submitLabel="Create draft" /></section>}
        {!selected && !identity.permission_keys.includes("catalog.write") && <p className="rounded-2xl border border-sand bg-white p-5 text-sm text-charcoal/75">Select a product to review its approved catalog details.</p>}
        {selected && <>
          <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="heading-sm">{selected.title}</h2><p className="mt-1 text-xs text-charcoal/75">/{selected.slug} · Updated {new Date(selected.updated_at).toLocaleString()}</p></div><span className="rounded-full bg-cream px-3 py-1 text-xs">{selected.status}</span></div>
            {identity.permission_keys.includes("catalog.write") && selected.status !== "ARCHIVED" ? <ProductFormFields value={productForm} onChange={setProductForm} allowStatus busy={busy} onSubmit={saveProduct} submitLabel="Save product" /> : <ProductReadOnly product={selected} />}
            {identity.permission_keys.includes("catalog.archive") && selected.status !== "ARCHIVED" && <button type="button" disabled={busy} onClick={() => void archiveProduct()} className="rounded-lg border border-rust/50 px-4 py-2 text-sm text-rust disabled:opacity-50">Archive product</button>}
          </section>
          <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
            <div><h2 className="font-medium">Variants and prices</h2><p className="mt-1 text-xs text-charcoal/75">Prices use PKR minor units internally and retain accepted order snapshots.</p></div>
            {selected.variants.length ? <ul className="space-y-3">{selected.variants.map((variant) => <VariantEditor key={variant.id} variant={variant} busy={busy || !identity.permission_keys.includes("catalog.write") || selected.status === "ARCHIVED"} onSave={updateVariant} />)}</ul> : <p className="text-sm text-charcoal/75">No sellable variants yet.</p>}
            {identity.permission_keys.includes("catalog.write") && selected.status !== "ARCHIVED" && <form onSubmit={(event) => void addVariant(event)} className="grid gap-3 border-t border-sand pt-4 sm:grid-cols-2">
              <label className="text-sm">SKU<input required maxLength={100} value={variantForm.sku} onChange={(event) => setVariantForm({ ...variantForm, sku: event.target.value })} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Color / option<input required maxLength={255} value={variantForm.color_name} onChange={(event) => setVariantForm({ ...variantForm, color_name: event.target.value })} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Color swatch<input type="color" value={variantForm.color_hex || "#8A5A44"} onChange={(event) => setVariantForm({ ...variantForm, color_hex: event.target.value })} className="mt-1 block h-10 w-full rounded-lg border border-sand p-1" /></label>
              <label className="text-sm">Price (PKR)<input required type="number" min="0" step="0.01" value={variantForm.price_minor !== "" ? (Number(variantForm.price_minor) / 100).toFixed(2) : ""} onChange={(event) => setVariantForm({ ...variantForm, price_minor: event.target.value ? String(Math.round(Number(event.target.value) * 100)) : "" })} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm sm:col-span-2">Sale price (optional, PKR)<input type="number" min="0" step="0.01" value={variantForm.sale_price_minor !== "" ? (Number(variantForm.sale_price_minor) / 100).toFixed(2) : ""} onChange={(event) => setVariantForm({ ...variantForm, sale_price_minor: event.target.value ? String(Math.round(Number(event.target.value) * 100)) : "" })} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2">Add variant</button>
            </form>}
          </section>
          <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
            <div><h2 className="font-medium">Product imagery</h2><p className="mt-1 text-sm text-charcoal/75">Attach the key of an existing image; this does not upload a file. On a published product, its media metadata including the object key is visible in the public catalog API. The storefront currently renders local /images assets only; external storage delivery is not configured.</p></div>
            {selected.media.length ? <ul className="space-y-2">{selected.media.slice().sort((first, second) => first.sort_order - second.sort_order).map((media) => <li key={media.id} className="rounded-lg bg-cream/70 p-3 text-sm"><span className="font-medium">{media.object_key}</span>{media.is_primary && <span className="ml-2 rounded-full bg-white px-2 py-1 text-[10px] uppercase tracking-wide text-charcoal/75">Primary</span>}<p className="mt-1 text-xs text-charcoal/75">{media.media_type}{media.width && media.height ? ` · ${media.width} × ${media.height}` : ""}{media.alt_text ? ` · ${media.alt_text}` : ""}</p></li>)}</ul> : <p className="text-sm text-charcoal/75">No media is attached. The storefront will use its placeholder image.</p>}
            {identity.permission_keys.includes("catalog.write") && selected.status !== "ARCHIVED" && <form onSubmit={(event) => void attachMedia(event)} className="grid gap-3 border-t border-sand pt-4 sm:grid-cols-2">
              <label className="text-sm sm:col-span-2">Existing object key<input name="object_key" required maxLength={500} placeholder="/images/products/example-front.webp" className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Media type<select name="media_type" defaultValue="image/webp" className="mt-1 block w-full rounded-lg border border-sand bg-white p-2"><option value="image/webp">WebP image</option><option value="image/jpeg">JPEG image</option><option value="image/png">PNG image</option></select></label>
              <label className="text-sm">Alternative text<input name="alt_text" maxLength={500} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Width in pixels<input name="width" type="number" min="1" step="1" className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Height in pixels<input name="height" type="number" min="1" step="1" className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="text-sm">Display order<input name="sort_order" type="number" min="0" step="1" defaultValue="0" className="mt-1 block w-full rounded-lg border border-sand p-2" /></label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm"><input name="is_primary" type="checkbox" />Set as primary image</label>
              <button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2">{busy ? "Attaching media…" : "Attach existing media"}</button>
            </form>}
          </section>
        </>}
      </div>
    </div>
  </div>;
}

function productPayload(value: ProductForm, expectedUpdatedAt?: string) {
  return {
    slug: value.slug.trim(),
    title: value.title.trim(),
    description: value.description,
    fabric: value.fabric,
    care: value.care,
    dimensions: value.dimensions,
    ...(expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt, status: value.status } : {}),
  };
}

function ProductFormFields({ value, onChange, allowStatus, busy, onSubmit, submitLabel }: {
  value: ProductForm;
  onChange: (value: ProductForm) => void;
  allowStatus: boolean;
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel: string;
}) {
  const field = (key: keyof ProductForm, label: string, multiline = false) => <label className="text-sm" key={key}>{label}{multiline ? <textarea rows={3} value={value[key]} onChange={(event) => onChange({ ...value, [key]: event.target.value })} className="mt-1 block w-full rounded-lg border border-sand p-2" /> : <input value={value[key]} onChange={(event) => onChange({ ...value, [key]: event.target.value })} className="mt-1 block w-full rounded-lg border border-sand p-2" />}</label>;
  return <form onSubmit={onSubmit} className="mt-4 grid gap-3 sm:grid-cols-2">
    {field("slug", "Slug")}{field("title", "Title")}{field("description", "Description", true)}{field("fabric", "Fabric")}{field("care", "Care instructions", true)}{field("dimensions", "Dimensions")}
    {allowStatus && <label className="text-sm">Visibility<select value={value.status} onChange={(event) => onChange({ ...value, status: event.target.value as ProductForm["status"] })} className="mt-1 block w-full rounded-lg border border-sand bg-white p-2"><option value="DRAFT">Draft</option><option value="PUBLISHED">Published</option></select></label>}
    <button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2">{busy ? "Saving…" : submitLabel}</button>
  </form>;
}

function ProductReadOnly({ product }: { product: ProductDetail }) {
  return <dl className="grid gap-3 text-sm sm:grid-cols-2">{(["description", "fabric", "care", "dimensions"] as const).map((key) => <div key={key}><dt className="text-xs uppercase text-charcoal/75">{key}</dt><dd className="mt-1 whitespace-pre-wrap">{product[key] || "—"}</dd></div>)}</dl>;
}

function VariantEditor({ variant, busy, onSave }: {
  variant: Variant;
  busy: boolean;
  onSave: (variant: Variant, changes: Partial<Variant>) => Promise<void>;
}) {
  const [price, setPrice] = useState((variant.price_minor / 100).toFixed(2));
  const [salePrice, setSalePrice] = useState(variant.sale_price_minor === null ? "" : (variant.sale_price_minor / 100).toFixed(2));
  return <li className="rounded-xl border border-sand/70 p-3">
    <div className="flex items-center justify-between gap-2"><div><p className="font-medium">{variant.sku} · {variant.color_name}</p><p className="text-xs text-charcoal/75">Current {money(variant.sale_price_minor ?? variant.price_minor)} · {variant.is_active ? "active" : "inactive"}</p></div><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={variant.is_active} onChange={(event) => void onSave(variant, { is_active: event.target.checked })} disabled={busy} />Active</label></div>
    <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]"><label className="text-xs">Price (PKR)<input type="number" min="0" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-2 text-sm" /></label><label className="text-xs">Sale price (PKR)<input type="number" min="0" step="0.01" value={salePrice} onChange={(event) => setSalePrice(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-2 text-sm" /></label><button type="button" disabled={busy} onClick={() => void onSave(variant, { price_minor: Math.round(Number(price) * 100), sale_price_minor: salePrice ? Math.round(Number(salePrice) * 100) : null })} className="self-end rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Save price</button></div>
  </li>;
}
