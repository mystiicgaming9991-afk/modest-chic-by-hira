import { describe, it, expect } from "vitest";
import { formatPrice, products, collections, categories } from "@/lib/data";

describe("formatPrice", () => {
  it("formats PKR amounts with separator", () => {
    expect(formatPrice(1850)).toBe("Rs. 1,850");
  });

  it("formats zero", () => {
    expect(formatPrice(0)).toBe("Rs. 0");
  });

  it("formats large numbers", () => {
    expect(formatPrice(100000)).toBe("Rs. 100,000");
  });

  it("formats fractional amounts as integers", () => {
    expect(formatPrice(2450)).toBe("Rs. 2,450");
  });
});

describe("products", () => {
  it("has at least 8 products", () => {
    expect(products.length).toBeGreaterThanOrEqual(8);
  });

  it("every product has a slug", () => {
    expect(products.every((p) => typeof p.slug === "string" && p.slug.length > 0)).toBe(true);
  });

  it("every product has at least one variant", () => {
    expect(products.every((p) => p.variants.length >= 1)).toBe(true);
  });

  it("every variant has a positive price", () => {
    for (const p of products) {
      for (const v of p.variants) {
        expect(v.price).toBeGreaterThan(0);
      }
    }
  });

  it("sale price is less than normal price when set", () => {
    for (const p of products) {
      for (const v of p.variants) {
        if (v.salePrice !== undefined) {
          expect(v.salePrice).toBeLessThan(v.price);
        }
      }
    }
  });
});

describe("collections", () => {
  it("has at least 3 collections", () => {
    expect(collections.length).toBeGreaterThanOrEqual(3);
  });

  it("every collection has a unique slug", () => {
    const slugs = collections.map((c) => c.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});

describe("categories", () => {
  it("has at least 2 categories", () => {
    expect(categories.length).toBeGreaterThanOrEqual(2);
  });

  it("every category has a unique slug", () => {
    const slugs = categories.map((c) => c.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});