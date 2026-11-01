import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { validateCatalog } from './validate-catalog.mjs';

export const catalogueQuery = `{
  "products": *[_type == "product" && !(_id in path("drafts.**")) && !(_id in path("versions.**"))] | order(title asc) {
    _id, "slug": slug.current, title, description, fabric, dimensions, care,
    "category": category->slug.current, "collections": collections[]->slug.current,
    tags, variants, isNew, isBestSeller, isFeatured,
    "photo": {"assetId": photo.asset._ref, "alt": photo.alt, "note": photo.note}
  },
  "categories": *[_type == "category" && !(_id in path("drafts.**")) && !(_id in path("versions.**"))] | order(title asc) {
    _id, "slug": slug.current, title, description, "assetId": image.asset._ref
  },
  "collections": *[_type == "collection" && !(_id in path("drafts.**")) && !(_id in path("versions.**"))] | order(title asc) {
    _id, "slug": slug.current, title, description, "assetId": image.asset._ref
  }
}`;

export async function readCatalogueConfig(root, env = process.env) {
  const config = JSON.parse(await readFile(path.join(root, 'catalogue.config.json'), 'utf8'));
  const source = env.STOREFRONT_CATALOG_SOURCE ?? config.source;
  if (!['file', 'sanity'].includes(source)) throw new Error('Catalogue source must be file or sanity.');
  if (source === 'sanity' && (!/^[a-z0-9]+$/.test(config.projectId ?? '') || !/^[a-z0-9][a-z0-9_-]*$/.test(config.dataset ?? '') || !/^\d{4}-\d{2}-\d{2}$/.test(config.apiVersion ?? ''))) {
    throw new Error('Sanity catalogue needs a valid projectId, dataset and dated apiVersion in catalogue.config.json.');
  }
  return { ...config, source };
}

async function responseBytes(response, limit, label) {
  if (Number(response.headers.get('content-length')) > limit) throw new Error(`${label} exceeds the download size limit.`);
  const chunks = [];
  let length = 0;
  for await (const chunk of response.body) {
    length += chunk.length;
    if (length > limit) throw new Error(`${label} exceeds the download size limit.`);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

export function sanityImageUrl(assetId, config) {
  const match = /^image-([a-zA-Z0-9]+)-(\d+x\d+)-(jpg|jpeg|png|webp|gif|avif)$/.exec(assetId ?? '');
  if (!match) throw new Error('Sanity catalogue: add a supported JPG, PNG, WebP, GIF or AVIF product photograph.');
  const url = new URL(`https://cdn.sanity.io/images/${config.projectId}/${config.dataset}/${match[1]}-${match[2]}.${match[3]}`);
  url.search = new URLSearchParams({ w: '1400', fit: 'max', fm: 'webp', q: '82' }).toString();
  return url;
}

export async function importSanityCatalog(stage, config, { fetchImpl = fetch } = {}) {
  const endpoint = new URL(`https://${config.projectId}.api.sanity.io/v${config.apiVersion}/data/query/${config.dataset}`);
  endpoint.search = new URLSearchParams({ query: catalogueQuery, perspective: 'published', returnQuery: 'false' }).toString();
  // Uncached, public, published-only reads. Never use a browser/admin token here.
  const response = await fetchImpl(endpoint, { signal: AbortSignal.timeout(20000), redirect: 'error' });
  if (!response.ok) throw new Error(`Sanity catalogue could not be fetched (HTTP ${response.status}). Build stopped; no fallback catalogue will be published.`);
  const body = JSON.parse((await responseBytes(response, 10 * 1024 * 1024, 'Sanity catalogue')).toString('utf8'));
  const data = body.result;
  if (!data || !['products', 'categories', 'collections'].every((key) => Array.isArray(data[key]))) {
    throw new Error('Sanity catalogue: invalid query response.');
  }
  for (const kind of ['products', 'categories', 'collections']) {
    for (const row of data[kind]) {
      if (!row || typeof row._id !== 'string' || row._id.includes('.')) throw new Error('Sanity catalogue: unpublished or invalid document returned.');
    }
  }
  const images = new Map();
  const imageDirectory = path.join(stage, 'public/images/catalogue');
  await mkdir(imageDirectory, { recursive: true });
  async function image(assetId) {
    if (images.has(assetId)) return images.get(assetId);
    const url = sanityImageUrl(assetId, config);
    const name = `${createHash('sha256').update(url.href).digest('hex').slice(0, 24)}.webp`;
    const result = await fetchImpl(url, { signal: AbortSignal.timeout(20000), redirect: 'error' });
    if (!result.ok) throw new Error(`Sanity photograph could not be fetched (HTTP ${result.status}).`);
    const bytes = await responseBytes(result, 5 * 1024 * 1024, 'Sanity photograph');
    if (!result.headers.get('content-type')?.startsWith('image/webp') || bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WEBP') {
      throw new Error('Sanity photograph download was not a WebP image.');
    }
    await writeFile(path.join(imageDirectory, name), bytes);
    const local = `/images/catalogue/${name}`;
    images.set(assetId, local);
    return local;
  }
  const catalogue = { products: [], categories: [], collections: [] };
  for (const kind of ['categories', 'collections']) {
    for (const row of data[kind]) catalogue[kind].push({
      id: row._id, slug: row.slug, title: row.title, description: row.description ?? '',
      image: row.assetId ? await image(row.assetId) : '/images/modest-chic-color-edit.webp', productCount: 0,
    });
  }
  for (const row of data.products) {
    if (!Array.isArray(row.variants) || row.variants.some((variant) => typeof variant?._key !== 'string' || !variant._key)) {
      throw new Error(`Sanity catalogue: ${row.title ?? row._id} needs variants with stable keys.`);
    }
    catalogue.products.push({
      id: row._id, slug: row.slug, title: row.title, description: row.description,
      fabric: row.fabric, dimensions: row.dimensions, care: row.care,
      category: row.category, categories: [row.category], collections: row.collections ?? [], tags: row.tags ?? [],
      variants: row.variants.map((variant) => ({
        id: `${row._id}.${variant._key}`, name: variant.name, color: variant.name, colorHex: variant.colorHex,
        sku: variant.sku, price: variant.price, ...(variant.salePrice == null ? {} : { salePrice: variant.salePrice }), stock: variant.stock,
      })),
      displayImage: await image(row.photo?.assetId), displayImageAlt: row.photo?.alt,
      displayImageKind: 'product', displayImageNote: row.photo?.note,
      rating: 0, reviewCount: 0,
      isNew: row.isNew ?? false, isBestSeller: row.isBestSeller ?? false, isFeatured: row.isFeatured ?? false,
    });
  }
  await writeFile(path.join(stage, 'src/content/catalog.json'), `${JSON.stringify(catalogue, null, 2)}\n`);
  const validated = await validateCatalog(stage);
  console.log(`Sanity catalogue ready: ${validated.products.length} published products, ${images.size} photographs.`);
  return validated;
}
