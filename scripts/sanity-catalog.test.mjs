import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { catalogueQuery, importSanityCatalog, readCatalogueConfig, sanityImageUrl } from './sanity-catalog.mjs';

const config = { source: 'sanity', projectId: 'project123', dataset: 'production', apiVersion: '2025-02-19' };
const asset = 'image-abcdef123-1200x800-jpg';
function fixture() {
  return {
    products: [{
      _id: 'product-scarf', slug: 'rose-scarf', title: 'Rose & Gold Scarf', description: 'A real product description.',
      fabric: 'Chiffon', dimensions: '180 x 70 cm', care: 'Hand wash.', category: 'hijabs', collections: ['new-arrivals'],
      photo: { assetId: asset, alt: 'Rose scarf', note: 'Product photograph.' },
      variants: [{ _key: 'rose', name: 'Rose & Gold', colorHex: '#C8B5AD', sku: 'ROSE-001', price: 1500, salePrice: 1250, stock: 3 }],
      isNew: true, isFeatured: true,
    }],
    categories: [{ _id: 'category-hijabs', slug: 'hijabs', title: 'Hijabs', assetId: asset }],
    collections: [{ _id: 'collection-new', slug: 'new-arrivals', title: 'New Arrivals' }],
  };
}
async function setup(t) {
  const stage = await mkdtemp(path.join(os.tmpdir(), 'modest-sanity-test-'));
  t.after(() => rm(stage, { recursive: true, force: true }));
  await mkdir(path.join(stage, 'src/content'), { recursive: true });
  await mkdir(path.join(stage, 'public/images'), { recursive: true });
  await writeFile(path.join(stage, 'public/images/modest-chic-color-edit.webp'), 'local group artwork');
  return stage;
}
function mockFetch(data, calls = []) {
  return async (url, options) => {
    calls.push({ url: new URL(url), options });
    if (url.hostname.endsWith('.api.sanity.io')) return Response.json({ result: data });
    return new Response(Buffer.from('RIFF1234WEBPfixture'), { headers: { 'content-type': 'image/webp' } });
  };
}

test('imports published products with stable variant IDs and local optimized photographs', async (t) => {
  const stage = await setup(t);
  const calls = [];
  const result = await importSanityCatalog(stage, config, { fetchImpl: mockFetch(fixture(), calls) });
  const product = result.products[0];
  assert.equal(product.variants[0].id, 'product-scarf.rose');
  assert.equal(product.variants[0].salePrice, 1250);
  assert.equal(product.variants[0].stock, 3);
  assert.equal(product.rating, 0);
  assert.equal(product.reviewCount, 0);
  assert.equal(product.isBestSeller, false);
  assert.equal(product.displayImageKind, 'product');
  assert.match(product.displayImage, /^\/images\/catalogue\/[a-f0-9]{24}\.webp$/);
  assert.equal(product.displayImage, result.categories[0].image);
  assert.equal(calls.length, 2, 'Shared image is downloaded only once');
  assert.equal(calls[0].url.searchParams.get('perspective'), 'published');
  assert.equal(calls[0].options.headers, undefined, 'No secret or token goes to public catalogue reads');
  assert.equal(calls[1].url.hostname, 'cdn.sanity.io');
  assert.equal(calls[1].url.searchParams.get('fm'), 'webp');
  assert.equal(calls[1].url.searchParams.get('w'), '1400');
  assert.ok((await readFile(path.join(stage, 'public', product.displayImage))).length > 0);
  assert.deepEqual(JSON.parse(await readFile(path.join(stage, 'src/content/catalog.json'), 'utf8')), result);
});

test('accepts an intentionally empty published catalogue', async (t) => {
  const stage = await setup(t);
  const result = await importSanityCatalog(stage, config, { fetchImpl: mockFetch({ products: [], categories: [], collections: [] }) });
  assert.equal(result.products.length, 0);
});

test('rejects drafts and malformed query results instead of presenting them as live products', async (t) => {
  const stage = await setup(t);
  const draft = fixture();
  draft.products[0]._id = 'drafts.product.scarf';
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch(draft) }), /unpublished/);
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch({ products: [] }) }), /invalid query response/);
  assert.ok(catalogueQuery.includes('drafts.**'));
  assert.ok(catalogueQuery.includes('versions.**'));
});

test('fails for unresolved references, invalid prices, duplicate SKUs and missing product photos', async (t) => {
  const stage = await setup(t);
  const missingCategory = fixture();
  missingCategory.products[0].category = null;
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch(missingCategory) }), /unknown category/);
  const price = fixture();
  price.products[0].variants[0].price = -1;
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch(price) }), /price must be positive/);
  const duplicate = fixture();
  duplicate.products[0].variants.push({ ...duplicate.products[0].variants[0], _key: 'blue' });
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch(duplicate) }), /duplicate or missing variant ID\/SKU/);
  const photo = fixture();
  photo.products[0].photo = null;
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: mockFetch(photo) }), /product photograph/);
});

test('does not fall back to a local or empty catalogue on an upstream failure', async (t) => {
  const stage = await setup(t);
  const original = '{"products":["previous build"]}';
  await writeFile(path.join(stage, 'src/content/catalog.json'), original);
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: async () => new Response('failure', { status: 503 }) }), /HTTP 503/);
  assert.equal(await readFile(path.join(stage, 'src/content/catalog.json'), 'utf8'), original);
});

test('rejects unexpected asset locations, SVGs and invalid image responses', async (t) => {
  const stage = await setup(t);
  for (const id of ['https://attacker.example/photo.jpg', '../secret', 'image-abcdef-1x1-svg']) assert.throws(() => sanityImageUrl(id, config), /photograph/);
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: async (url) => url.hostname.endsWith('.api.sanity.io')
    ? Response.json({ result: fixture() }) : new Response('<html>not a photo</html>', { headers: { 'content-type': 'text/html' } }) }), /not a WebP/);
});

test('enforces download limits and fails missing image downloads', async (t) => {
  const stage = await setup(t);
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: async () => new Response('large', { headers: { 'content-length': String(11 * 1024 * 1024) } }) }), /size limit/);
  await assert.rejects(importSanityCatalog(stage, config, { fetchImpl: async (url) => url.hostname.endsWith('.api.sanity.io')
    ? Response.json({ result: fixture() }) : new Response('missing', { status: 404 }) }), /photograph.*404/);
});

test('selects an explicit source and rejects incomplete Sanity settings', async (t) => {
  const stage = await setup(t);
  await writeFile(path.join(stage, 'catalogue.config.json'), JSON.stringify(config));
  assert.equal((await readCatalogueConfig(stage, {})).source, 'sanity');
  assert.equal((await readCatalogueConfig(stage, { STOREFRONT_CATALOG_SOURCE: 'file' })).source, 'file');
  await writeFile(path.join(stage, 'catalogue.config.json'), JSON.stringify({ ...config, projectId: '../bad' }));
  await assert.rejects(readCatalogueConfig(stage, {}), /valid projectId/);
  await assert.rejects(readCatalogueConfig(stage, { STOREFRONT_CATALOG_SOURCE: 'unknown' }), /source/);
});
