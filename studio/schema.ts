import { defineArrayMember, defineField, defineType } from 'sanity';

const title = () => defineField({ name: 'title', title: 'Name', type: 'string', validation: (r) => r.required().min(1).max(160) });
const slug = () => defineField({
  name: 'slug', type: 'slug', title: 'Product / category link', options: { source: 'title' },
  description: 'Generate this once. Keep it unchanged after publishing so shared links continue to work.',
  validation: (r) => r.required().custom((value) => !value?.current || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value.current) || 'Use lowercase words separated by hyphens.'),
});
const text = (name: string, label: string) => defineField({ name, title: label, type: 'text', rows: 3, validation: (r) => r.required().min(1) });

const photo = defineType({
  name: 'cataloguePhoto', title: 'Product photograph', type: 'image',
  options: { accept: 'image/jpeg,image/png,image/webp,image/gif,image/avif' },
  fields: [
    defineField({ name: 'alt', title: 'Describe this photograph', type: 'string', description: 'For example: rose chiffon hijab laid flat. Used for accessibility.', validation: (r) => r.required().min(1) }),
    defineField({ name: 'note', title: 'Photo note', type: 'string', initialValue: 'Product photograph; colours may vary by screen.', validation: (r) => r.required().min(1) }),
  ],
});
const variant = defineType({
  name: 'productVariant', title: 'Colour / variant', type: 'object',
  fields: [
    defineField({ name: 'name', title: 'Colour / variant name', type: 'string', validation: (r) => r.required().min(1) }),
    defineField({ name: 'colorHex', title: 'Colour swatch (hex)', type: 'string', initialValue: '#D4C5B9', validation: (r) => r.required().regex(/^#[a-fA-F0-9]{6}$/) }),
    defineField({ name: 'sku', title: 'SKU', type: 'string', description: 'A unique code for this variant. Keep it stable after publishing.', validation: (r) => r.required().min(1) }),
    defineField({ name: 'price', title: 'Price (PKR)', type: 'number', validation: (r) => r.required().min(0.01).precision(2) }),
    defineField({ name: 'salePrice', title: 'Sale price (PKR, optional)', type: 'number', validation: (r) => r.min(0).precision(2).custom((value, context) => {
      const parent = context.parent as { price?: number } | undefined;
      return value == null || parent?.price == null || value <= parent.price || 'Sale price cannot exceed the regular price.';
    }) }),
    defineField({ name: 'stock', title: 'Available quantity', type: 'number', initialValue: 0, description: 'Update after confirming a WhatsApp order. Zero displays sold out; the website does not reserve stock.', validation: (r) => r.required().integer().min(0) }),
  ],
  preview: { select: { title: 'name', subtitle: 'sku' } },
});
const product = defineType({
  name: 'product', title: 'Product', type: 'document',
  initialValue: { isNew: false, isBestSeller: false, isFeatured: false, collections: [], tags: [] },
  fields: [
    title(), slug(), text('description', 'Description'), text('fabric', 'Fabric'), text('dimensions', 'Dimensions'), text('care', 'Care instructions'),
    defineField({ name: 'category', title: 'Category', type: 'reference', to: [{ type: 'category' }], description: 'Publish the category before publishing this product.', validation: (r) => r.required() }),
    defineField({ name: 'collections', title: 'Collections', type: 'array', of: [defineArrayMember({ type: 'reference', to: [{ type: 'collection' }] })], validation: (r) => r.unique() }),
    defineField({ name: 'photo', title: 'Product photograph', type: 'cataloguePhoto', validation: (r) => r.required().custom((value) => Boolean((value as { asset?: { _ref?: string } } | undefined)?.asset?._ref) || 'Upload a real product photograph before publishing.') }),
    defineField({ name: 'variants', title: 'Colours and prices', type: 'array', of: [defineArrayMember({ type: 'productVariant' })], validation: (r) => r.required().min(1).custom((value) => {
      if (!Array.isArray(value)) return true;
      const skus = value.map((entry) => (entry as { sku?: string }).sku).filter(Boolean);
      return new Set(skus).size === skus.length || 'Every variant needs a different SKU.';
    }) }),
    defineField({ name: 'tags', type: 'array', of: [{ type: 'string' }], options: { layout: 'tags' } }),
    defineField({ name: 'isNew', title: 'Show New badge', type: 'boolean' }),
    defineField({ name: 'isBestSeller', title: 'Best seller', type: 'boolean' }),
    defineField({ name: 'isFeatured', title: 'Feature on the homepage', type: 'boolean' }),
  ],
  preview: { select: { title: 'title', media: 'photo' } },
});

const group = (name: 'category' | 'collection', label: string) => defineType({
  name, title: label, type: 'document',
  fields: [
    title(), slug(),
    defineField({ name: 'description', title: 'Description', type: 'text', rows: 3 }),
    defineField({ name: 'image', title: 'Cover photo (optional)', type: 'image', options: { accept: 'image/jpeg,image/png,image/webp,image/gif,image/avif' }, description: 'If empty, the existing Modest Chic collection artwork is used.' }),
  ],
  preview: { select: { title: 'title', media: 'image' } },
});

export const schemaTypes = [photo, variant, product, group('category', 'Category'), group('collection', 'Collection')];
