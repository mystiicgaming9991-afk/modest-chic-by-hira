import type { Product } from "@/lib/data";

export function productImageLabel(kind: Product["displayImageKind"]): string {
  return { product: "Product photo", brand: "Collection photo", reference: "Style reference", illustration: "Illustrative image" }[kind];
}
