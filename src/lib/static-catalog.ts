import content from "@/content/catalog.json";
import type { Product, Category, Collection } from "@/lib/data";

const catalog = content as { products: Product[]; categories: Category[]; collections: Collection[] };
export const staticCatalog = {
  ...catalog,
  categories: catalog.categories.map((category) => ({ ...category, productCount: catalog.products.filter((product) => (product.categories ?? [product.category]).includes(category.slug)).length })),
  collections: catalog.collections.map((collection) => ({ ...collection, productCount: catalog.products.filter((product) => product.collections?.includes(collection.slug)).length })),
};
