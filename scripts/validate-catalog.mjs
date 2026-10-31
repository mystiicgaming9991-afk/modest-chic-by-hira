import { readFile, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export async function validateCatalog(root) {
  const catalog = JSON.parse(await readFile(path.join(root, 'src/content/catalog.json'), 'utf8'));
  const fail = (message) => { throw new Error(`Catalogue: ${message}`); };
  const text = (value) => typeof value === 'string' && value.trim().length > 0;
  const slug = (value) => text(value) && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
  const unique = (rows, field, label) => {
    const keys = rows.map((row) => row[field]);
    if (keys.some((key) => !text(key)) || new Set(keys).size !== keys.length) fail(`${label} need unique, nonempty ${field} values`);
  };
  const image = async (value) => {
    if (!text(value) || !value.startsWith('/images/') || value.includes('..')) fail(`invalid image path ${value}`);
    try { await access(path.join(root, 'public', value)); } catch { fail(`image does not exist: ${value}`); }
  };
  for (const key of ['products', 'categories', 'collections']) {
    if (!Array.isArray(catalog[key])) fail(`${key} must be an array`);
    unique(catalog[key], 'id', key);
    unique(catalog[key], 'slug', key);
    for (const row of catalog[key]) {
      if (!slug(row.slug) || !text(row.title)) fail(`${key} need a URL slug and title`);
      await image(key === 'products' ? row.displayImage : row.image);
    }
  }
  const variantIds = new Set();
  const skus = new Set();
  for (const product of catalog.products) {
    for (const key of ['description', 'fabric', 'dimensions', 'care', 'displayImageAlt']) if (!text(product[key])) fail(`${product.slug}: ${key} is required`);
    if (!catalog.categories.some((item) => item.slug === product.category)) fail(`${product.slug}: unknown category`);
    if (!Array.isArray(product.collections) || product.collections.some((key) => !catalog.collections.some((item) => item.slug === key))) fail(`${product.slug}: unknown collection`);
    for (const key of ['isNew', 'isBestSeller', 'isFeatured']) if (typeof product[key] !== 'boolean') fail(`${product.slug}: ${key} must be true or false`);
    if (product.rating !== 0 || product.reviewCount !== 0) fail(`${product.slug}: do not publish unverified ratings; keep rating and reviewCount at 0`);
    if (!text(product.displayImageNote)) fail(`${product.slug}: describe the image accurately`);
    if (!Array.isArray(product.tags) || !Array.isArray(product.variants) || !product.variants.length) fail(`${product.slug}: tags and at least one variant are required`);
    if (!['brand', 'reference', 'illustration'].includes(product.displayImageKind)) fail(`${product.slug}: invalid image kind`);
    if (product.displayImage.includes('product-placeholder')) fail(`${product.slug}: add a real catalogue image before publishing`);
    for (const variant of product.variants) {
      if (!text(variant.id) || variantIds.has(variant.id) || !text(variant.sku) || skus.has(variant.sku)) fail(`${product.slug}: duplicate or missing variant ID/SKU`);
      variantIds.add(variant.id); skus.add(variant.sku);
      if (!text(variant.name) || !text(variant.color) || !/^#[a-fA-F0-9]{6}$/.test(variant.colorHex)) fail(`${product.slug}: variant shade and colour are required`);
      if (!Number.isFinite(variant.price) || variant.price <= 0 || !Number.isSafeInteger(Math.round(variant.price * 100))) fail(`${product.slug}: price must be positive`);
      if (variant.salePrice !== undefined && (!Number.isFinite(variant.salePrice) || variant.salePrice < 0 || variant.salePrice > variant.price)) fail(`${product.slug}: invalid sale price`);
      if (!Number.isSafeInteger(variant.stock) || variant.stock < 0) fail(`${product.slug}: stock must be a nonnegative integer`);
    }
  }
  return catalog;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const catalog = await validateCatalog(root);
  console.log(`Catalogue valid: ${catalog.products.length} products.`);
}
