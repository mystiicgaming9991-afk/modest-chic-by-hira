"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type Status = "DRAFT" | "PUBLISHED" | "ARCHIVED";
interface Category { id: string; slug: string; name: string; description: string | null; parent_id: string | null; sort_order: number; status: Status; created_at: string; updated_at: string; children: Category[] }
interface Collection { id: string; slug: string; name: string; description: string | null; status: Status; starts_at: string | null; ends_at: string | null; created_at: string; updated_at: string }
interface Tag { id: string; name: string }
interface Product { id: string; slug: string; title: string; status: Status; updated_at: string }

export default function CatalogGroupsPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<Category[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [collectionProductIds, setCollectionProductIds] = useState<string[]>([]);
  const [productToAdd, setProductToAdd] = useState("");
  const [selectedProductId, setSelectedProductId] = useState("");
  const [productCategoryIds, setProductCategoryIds] = useState<string[]>([]);
  const [categoryToAdd, setCategoryToAdd] = useState("");
  const [productTagIds, setProductTagIds] = useState<string[]>([]);
  const [tagToAdd, setTagToAdd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  useEffect(() => {
    if (!identity?.permission_keys.includes("catalog.read")) return;
    const timer = window.setTimeout(() => void loadCatalogGroups(), 0);
    return () => window.clearTimeout(timer);
    // Load catalogs after the authenticated permission check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity]);

  useEffect(() => {
    if (!selectedCollectionId) return;
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<string[]>(`admin/catalog/collections/${selectedCollectionId}/products`)
        .then((ids) => { if (active) setCollectionProductIds(ids); })
        .catch((cause) => {
          if (active) setError(cause instanceof Error ? cause.message : "Collection membership could not be loaded.");
        });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [selectedCollectionId]);

  useEffect(() => {
    if (!selectedProductId) return;
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<string[]>(`admin/catalog/products/${selectedProductId}/categories`)
        .then((ids) => { if (active) setProductCategoryIds(ids); })
        .catch((cause) => {
          if (active) setError(cause instanceof Error ? cause.message : "Product categories could not be loaded.");
        });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [selectedProductId]);

  useEffect(() => {
    if (!selectedProductId) return;
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<string[]>(`admin/catalog/products/${selectedProductId}/tags`)
        .then((ids) => { if (active) setProductTagIds(ids); })
        .catch((cause) => {
          if (active) setError(cause instanceof Error ? cause.message : "Product tags could not be loaded.");
        });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [selectedProductId]);

  async function loadCatalogGroups() {
    setBusy(true); setError(null);
    try {
      const [categoryResult, collectionResult, tagResult, productResult] = await Promise.all([
        staffJson<{ items: Category[] }>("admin/catalog/categories"),
        staffJson<{ items: Collection[] }>("admin/catalog/collections"),
        staffJson<{ items: Tag[] }>("admin/catalog/tags"),
        loadAllProducts(),
      ]);
      setCategories(categoryResult.items);
      setCollections(collectionResult.items);
      setTags(tagResult.items);
      setProducts(productResult);
      if (!selectedCollectionId && collectionResult.items[0]) setSelectedCollectionId(collectionResult.items[0].id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Catalog group data could not be loaded."); }
    finally { setBusy(false); }
  }

  async function loadAllProducts(): Promise<Product[]> {
    const all: Product[] = [];
    let cursor: string | null = null;
    do {
      const params = new URLSearchParams({ limit: "100" });
      if (cursor) params.set("after", cursor);
      const page = await staffJson<{ items: Product[]; next_cursor: string | null }>(`admin/catalog/products?${params}`);
      all.push(...page.items);
      cursor = page.next_cursor;
    } while (cursor);
    return all;
  }

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await staffJson<Category>("admin/catalog/categories", jsonBody({
        slug: String(form.get("slug")).trim(),
        name: String(form.get("name")).trim(),
        description: String(form.get("description") || ""),
        parent_id: String(form.get("parent_id") || "") || null,
        sort_order: Number(form.get("sort_order") || 0),
      }));
      formElement.reset();
      await loadCatalogGroups();
      setNotice("Category created as a draft.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Category could not be created."); }
    finally { setBusy(false); }
  }

  async function setCategoryStatus(category: Category, status: Status) {
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Category>(`admin/catalog/categories/${category.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, expected_updated_at: category.updated_at }),
      });
      await loadCatalogGroups();
      setNotice(`${category.name} is now ${status.toLowerCase()}.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Category could not be updated.";
      if (message.toLowerCase().includes("changed since it was loaded")) {
        await loadCatalogGroups();
        setError("This category changed in another session. The latest values are loaded; review and retry.");
      } else setError(message);
    }
    finally { setBusy(false); }
  }

  async function createCollection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const collection = await staffJson<Collection>("admin/catalog/collections", jsonBody({
        slug: String(form.get("slug")).trim(),
        name: String(form.get("name")).trim(),
        description: String(form.get("description") || ""),
      }));
      formElement.reset();
      await loadCatalogGroups();
      setSelectedCollectionId(collection.id);
      setNotice("Collection created as a draft.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Collection could not be created."); }
    finally { setBusy(false); }
  }

  async function saveCollectionStatus(status: Status) {
    const collection = collections.find((item) => item.id === selectedCollectionId);
    if (!collection) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<Collection>(`admin/catalog/collections/${collection.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, expected_updated_at: collection.updated_at }),
      });
      await loadCatalogGroups();
      setNotice(`Collection is now ${status.toLowerCase()}.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Collection could not be updated.";
      if (message.toLowerCase().includes("changed since it was loaded")) {
        await loadCatalogGroups();
        setError("This collection changed in another session. The latest values are loaded; review and retry.");
      } else setError(message);
    }
    finally { setBusy(false); }
  }

  async function saveCollectionProducts() {
    const collection = collections.find((item) => item.id === selectedCollectionId);
    if (!collection) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<void>(`admin/catalog/collections/${selectedCollectionId}/products`, {
        ...jsonBody({
          product_ids: collectionProductIds,
          expected_updated_at: collection.updated_at,
        }),
        method: "PUT",
      });
      await loadCatalogGroups();
      setNotice("Collection order saved.");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Collection order could not be saved.";
      if (message.toLowerCase().includes("changed since it was loaded")) {
        await loadCatalogGroups();
        const currentIds = await staffJson<string[]>(`admin/catalog/collections/${selectedCollectionId}/products`);
        setCollectionProductIds(currentIds);
        setError("This collection changed in another session. The latest values are loaded; review and retry.");
      } else setError(message);
    }
    finally { setBusy(false); }
  }

  async function saveProductCategories() {
    const product = products.find((item) => item.id === selectedProductId);
    if (!product) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<void>(`admin/catalog/products/${selectedProductId}/categories`, {
        ...jsonBody({
          category_ids: productCategoryIds,
          expected_updated_at: product.updated_at,
        }),
        method: "PUT",
      });
      await loadCatalogGroups();
      setNotice("Product categories saved in the displayed order.");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Product categories could not be saved.";
      if (message.toLowerCase().includes("changed since it was loaded")) {
        await loadCatalogGroups();
        const [categoryIds, tagIds] = await Promise.all([
          staffJson<string[]>(`admin/catalog/products/${selectedProductId}/categories`),
          staffJson<string[]>(`admin/catalog/products/${selectedProductId}/tags`),
        ]);
        setProductCategoryIds(categoryIds);
        setProductTagIds(tagIds);
        setError("This product changed in another session. The latest values are loaded; review and retry.");
      } else setError(message);
    }
    finally { setBusy(false); }
  }

  async function saveProductTags() {
    const product = products.find((item) => item.id === selectedProductId);
    if (!product) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await staffJson<void>(`admin/catalog/products/${selectedProductId}/tags`, {
        ...jsonBody({
          tag_ids: productTagIds,
          expected_updated_at: product.updated_at,
        }),
        method: "PUT",
      });
      await loadCatalogGroups();
      setNotice("Product tags saved.");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Product tags could not be saved.";
      if (message.toLowerCase().includes("changed since it was loaded")) {
        await loadCatalogGroups();
        const [categoryIds, tagIds] = await Promise.all([
          staffJson<string[]>(`admin/catalog/products/${selectedProductId}/categories`),
          staffJson<string[]>(`admin/catalog/products/${selectedProductId}/tags`),
        ]);
        setProductCategoryIds(categoryIds);
        setProductTagIds(tagIds);
        setError("This product changed in another session. The latest values are loaded; review and retry.");
      } else setError(message);
    }
    finally { setBusy(false); }
  }

  async function createTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await staffJson<Tag>("admin/catalog/tags", jsonBody({ name: String(form.get("name")).trim() }));
      formElement.reset();
      await loadCatalogGroups();
      setNotice("Tag created.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Tag could not be created."); }
    finally { setBusy(false); }
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("catalog.read")) return <p role="alert">Catalog access is not included in your permissions. <Link href="/admin" className="underline">Back to staff home</Link></p>;
  const canWrite = identity.permission_keys.includes("catalog.write");
  const flatCategories = flattenCategories(categories);
  const selectedCollection = collections.find((collection) => collection.id === selectedCollectionId);
  const availableProducts = products.filter((product) => !collectionProductIds.includes(product.id));

  return <div className="space-y-8">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-terracotta">Catalog administration</p><h1 className="heading-md mt-2">Categories and collections</h1><p className="mt-2 text-sm text-charcoal/75">Organize product discovery and set the visible order for each collection.</p></div><div className="flex gap-4 text-sm"><Link href="/admin/catalog" className="text-terracotta underline">Products</Link><Link href="/admin" className="text-terracotta underline">Staff home</Link></div></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="space-y-4 rounded-2xl border border-sand bg-white p-5"><h2 className="heading-sm">Categories</h2>
        {canWrite && <form onSubmit={(event) => void createCategory(event)} className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Name<input required name="name" maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><label className="text-sm">Slug<input required name="slug" maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><label className="text-sm">Parent category<select name="parent_id" className="mt-1 block w-full rounded-lg border border-sand bg-white p-2"><option value="">Top level</option>{flatCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label className="text-sm">Sort order<input name="sort_order" type="number" defaultValue="0" className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><label className="text-sm sm:col-span-2">Description<textarea name="description" rows={2} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2">Create draft category</button></form>}
        <ul className="space-y-2">{flatCategories.map((category) => <li key={category.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sand/70 p-3"><div><p className="font-medium">{category.name}</p><p className="text-xs text-charcoal/75">{category.slug} · order {category.sort_order} · {category.status}</p></div>{canWrite && category.status !== "ARCHIVED" && <select aria-label={`Visibility for ${category.name}`} value={category.status} disabled={busy} onChange={(event) => void setCategoryStatus(category, event.target.value as Status)} className="rounded-lg border border-sand bg-white p-2 text-xs"><option value="DRAFT">Draft</option><option value="PUBLISHED">Published</option></select>}</li>)}</ul>
        {!flatCategories.length && <p className="text-sm text-charcoal/75">No categories yet.</p>}
      </div>
      <div className="space-y-4 rounded-2xl border border-sand bg-white p-5"><h2 className="heading-sm">Collections</h2>
        {canWrite && <form onSubmit={(event) => void createCollection(event)} className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Name<input required name="name" maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><label className="text-sm">Slug<input required name="slug" maxLength={255} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><label className="text-sm sm:col-span-2">Description<textarea name="description" rows={2} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><button disabled={busy} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2">Create draft collection</button></form>}
        <label className="block text-sm">Selected collection<select value={selectedCollectionId} onChange={(event) => { setSelectedCollectionId(event.target.value); setCollectionProductIds([]); }} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">Choose a collection</option>{collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name} · {collection.status}</option>)}</select></label>
        {selectedCollection && <div className="space-y-4 rounded-xl border border-sand p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-medium">{selectedCollection.name}</h3><p className="text-xs text-charcoal/75">/{selectedCollection.slug} · {selectedCollection.status}</p></div>{canWrite && <select aria-label="Collection visibility" value={selectedCollection.status} disabled={busy} onChange={(event) => void saveCollectionStatus(event.target.value as Status)} className="rounded-lg border border-sand bg-white p-2 text-xs"><option value="DRAFT">Draft</option><option value="PUBLISHED">Published</option><option value="ARCHIVED">Archived</option></select>}</div>
          {canWrite && <div className="flex gap-2"><select aria-label="Add product to collection" value={productToAdd} onChange={(event) => setProductToAdd(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-sand bg-white p-2 text-sm"><option value="">Add a product…</option>{availableProducts.map((product) => <option key={product.id} value={product.id}>{product.title} · {product.status}</option>)}</select><button type="button" disabled={!productToAdd} onClick={() => { setCollectionProductIds((current) => [...current, productToAdd]); setProductToAdd(""); }} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Add</button></div>}
          <ol className="space-y-2">{collectionProductIds.map((productId, index) => {
            const product = products.find((item) => item.id === productId);
            return <li key={productId} className="flex items-center gap-2 rounded-lg bg-cream/70 p-3"><span className="w-6 text-xs text-charcoal/75">{index + 1}</span><span className="min-w-0 flex-1 truncate text-sm">{product ? `${product.title} · ${product.slug}` : `Unavailable product ${productId}`}</span>{canWrite && <><button type="button" disabled={busy || index === 0} onClick={() => setCollectionProductIds(moveItem(collectionProductIds, index, index - 1))} aria-label={`Move product ${index + 1} up`} className="rounded border border-sand px-2 py-1 text-xs disabled:opacity-40">↑</button><button type="button" disabled={busy || index === collectionProductIds.length - 1} onClick={() => setCollectionProductIds(moveItem(collectionProductIds, index, index + 1))} aria-label={`Move product ${index + 1} down`} className="rounded border border-sand px-2 py-1 text-xs disabled:opacity-40">↓</button><button type="button" disabled={busy} onClick={() => setCollectionProductIds(collectionProductIds.filter((id) => id !== productId))} aria-label={`Remove ${product?.title ?? "product"}`} className="rounded border border-rust/30 px-2 py-1 text-xs text-rust disabled:opacity-40">Remove</button></>}</li>;
          })}</ol>
          {canWrite && <button type="button" disabled={busy} onClick={() => void saveCollectionProducts()} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Save collection order</button>}
        </div>}
        {!collections.length && <p className="text-sm text-charcoal/75">No collections yet.</p>}
      </div>
    </section>
    <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
      <div><h2 className="heading-sm">Product category membership</h2><p className="mt-1 text-sm text-charcoal/75">Assign and order the categories a product appears under.</p></div>
      <label className="block max-w-xl text-sm">Product<select value={selectedProductId} onChange={(event) => { setSelectedProductId(event.target.value); setProductCategoryIds([]); setProductTagIds([]); }} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3"><option value="">Choose a product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.title} · {product.status}</option>)}</select></label>
      {selectedProductId && <div className="max-w-2xl space-y-3">
        {canWrite && <div className="flex gap-2"><select aria-label="Add category to product" value={categoryToAdd} onChange={(event) => setCategoryToAdd(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-sand bg-white p-2 text-sm"><option value="">Add a category…</option>{flatCategories.filter((category) => !productCategoryIds.includes(category.id)).map((category) => <option key={category.id} value={category.id}>{category.name} · {category.status}</option>)}</select><button type="button" disabled={!categoryToAdd} onClick={() => { setProductCategoryIds((current) => [...current, categoryToAdd]); setCategoryToAdd(""); }} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Add</button></div>}
        <ol className="space-y-2">{productCategoryIds.map((categoryId, index) => {
          const category = flatCategories.find((item) => item.id === categoryId);
          return <li key={categoryId} className="flex items-center gap-2 rounded-lg bg-cream/70 p-3"><span className="w-6 text-xs text-charcoal/75">{index + 1}</span><span className="min-w-0 flex-1 truncate text-sm">{category?.name ?? `Unavailable category ${categoryId}`}</span>{canWrite && <><button type="button" disabled={busy || index === 0} onClick={() => setProductCategoryIds(moveItem(productCategoryIds, index, index - 1))} aria-label={`Move category ${index + 1} up`} className="rounded border border-sand px-2 py-1 text-xs disabled:opacity-40">↑</button><button type="button" disabled={busy || index === productCategoryIds.length - 1} onClick={() => setProductCategoryIds(moveItem(productCategoryIds, index, index + 1))} aria-label={`Move category ${index + 1} down`} className="rounded border border-sand px-2 py-1 text-xs disabled:opacity-40">↓</button><button type="button" disabled={busy} onClick={() => setProductCategoryIds(productCategoryIds.filter((id) => id !== categoryId))} className="rounded border border-rust/30 px-2 py-1 text-xs text-rust disabled:opacity-40">Remove</button></>}</li>;
        })}</ol>
        {canWrite && <button type="button" disabled={busy} onClick={() => void saveProductCategories()} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Save category order</button>}
      </div>}
    </section>
    <section className="space-y-4 rounded-2xl border border-sand bg-white p-5">
      <div><h2 className="heading-sm">Product tags</h2><p className="mt-1 text-sm text-charcoal/75">Assign reusable tags to the selected product.</p></div>
      {selectedProductId ? <div className="max-w-2xl space-y-3">
        {canWrite && <div className="flex gap-2"><select aria-label="Add tag to product" value={tagToAdd} onChange={(event) => setTagToAdd(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-sand bg-white p-2 text-sm"><option value="">Add a tag…</option>{tags.filter((tag) => !productTagIds.includes(tag.id)).map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select><button type="button" disabled={!tagToAdd} onClick={() => { setProductTagIds((current) => [...current, tagToAdd]); setTagToAdd(""); }} className="rounded-lg border border-sand px-3 py-2 text-sm disabled:opacity-50">Add</button></div>}
        <ul className="flex flex-wrap gap-2">{productTagIds.map((tagId) => {
          const tag = tags.find((item) => item.id === tagId);
          return <li key={tagId} className="flex items-center gap-2 rounded-full border border-sand px-3 py-1 text-sm">{tag?.name ?? `Unavailable tag ${tagId}`}{canWrite && <button type="button" disabled={busy} onClick={() => setProductTagIds((current) => current.filter((id) => id !== tagId))} aria-label={`Remove ${tag?.name ?? "tag"}`} className="text-rust disabled:opacity-40">×</button>}</li>;
        })}</ul>
        {canWrite && <button type="button" disabled={busy} onClick={() => void saveProductTags()} className="rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Save product tags</button>}
      </div> : <p className="text-sm text-charcoal/75">Choose a product above to manage its tags.</p>}
      {canWrite && <form onSubmit={(event) => void createTag(event)} className="flex flex-wrap gap-3 border-t border-sand pt-4"><label className="min-w-56 flex-1 text-sm">Create a reusable tag<input required name="name" maxLength={100} className="mt-1 block w-full rounded-lg border border-sand p-2" /></label><button disabled={busy} className="self-end rounded-lg bg-charcoal px-4 py-2 text-sm text-white disabled:opacity-50">Create tag</button></form>}
      <ul className="flex flex-wrap gap-2">{tags.map((tag) => <li key={tag.id} className="rounded-full bg-cream px-3 py-1 text-xs text-charcoal/70">{tag.name}</li>)}</ul>
    </section>
    <Link href="/admin/catalog" className="inline-block text-sm text-terracotta underline">Back to catalog</Link>
  </div>;
}

function flattenCategories(categories: Category[]): Category[] {
  return categories.flatMap((category) => [category, ...flattenCategories(category.children)]);
}

function moveItem(items: string[], from: number, to: number): string[] {
  const reordered = [...items];
  const [item] = reordered.splice(from, 1);
  reordered.splice(to, 0, item);
  return reordered;
}
