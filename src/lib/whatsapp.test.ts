import { afterEach, describe, expect, it, vi } from "vitest";
import { cartEnquiry, contactEnquiry, productEnquiry, whatsappLink, whatsappNumber, type EnquiryLine } from "./whatsapp";
import type { Product, ProductVariant } from "./data";

const product = { title: "Silk & Satin", slug: "silk-satin", fabric: "Silk", dimensions: "180 x 70 cm", displayImage: "/images/catalog/silk.webp", displayImageKind: "brand" } as Product;
const variant = { name: "Rose / Gold", sku: "SILK-ROSE", price: 1500, salePrice: 1250 } as ProductVariant;

afterEach(() => vi.unstubAllEnvs());
const format = (n: number) => `Rs. ${n.toLocaleString("en-US")}`;

describe("WhatsApp enquiries", () => {
  it("uses distinct templates and the selected quantity and sale price", () => {
    const text = productEnquiry(product, variant, "https://shop.example", 3);
    expect(text).toContain("Product enquiry");
    expect(text).toContain("Quantity: 3");
    expect(text).toContain("Displayed price: Rs. 1,250 each");
    expect(text).toContain("Estimated item subtotal: Rs. 3,750");
    expect(text).toContain("SKU: SILK-ROSE");
    expect(text).toContain("Dimensions: 180 x 70 cm");
    expect(text).toContain("Photo: https://shop.example/images/catalog/silk.webp");
    expect(contactEnquiry()).toContain("General enquiry");
  });

  it("uses the deployed site origin for links and omits placeholder photos", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://modest.example/path");
    const text = productEnquiry({ ...product, displayImage: "/images/product-placeholder.svg" }, variant, "http://localhost:3001");
    expect(text).toContain("Product: https://modest.example/shop/silk-satin");
    expect(text).toContain("Photo: not available yet");
    expect(text).not.toContain("localhost");
    expect(text).not.toContain("product-placeholder.svg");
  });

  it("accepts only international digits and encodes prepared messages", () => {
    expect(whatsappNumber("923001234567")).toBe("923001234567");
    for (const invalid of [undefined, "", "+923001234567", "03001234567", "123-456", "123"]) {
      expect(whatsappNumber(invalid)).toBeNull();
    }
    const message = productEnquiry(product, variant, "https://shop.example");
    expect(message).toContain("Silk & Satin — Rose / Gold");
    expect(message).toContain("https://shop.example/shop/silk-satin");
    expect(new URL(whatsappLink("923001234567", message)).searchParams.get("text")).toBe(message);
  });

  it("includes all cart lines, prices and the estimated subtotal", () => {
    const lines = [
      { product, variant, quantity: 2, lineTotal: 2500 },
      { product: { ...product, title: "Cotton", slug: "cotton" }, variant: { ...variant, name: "Blue" }, quantity: 1, lineTotal: 1000 },
    ] as EnquiryLine[];
    const message = cartEnquiry(lines, 3500, "https://shop.example", format);
    expect(message).toContain("Silk & Satin — Rose / Gold");
    expect(message).toContain("Quantity: 2 | Price: Rs. 1,250 each | Subtotal: Rs. 2,500");
    expect(message).toContain("Cotton — Blue");
    expect(message).toContain("Cart order request");
    expect(message).toContain("Total quantity: 3");
    expect(message).toContain("*Item 2*");
    expect(message).toContain("https://shop.example/shop/cotton");
    expect(message).toContain("Estimated subtotal: Rs. 3,500");
    expect(message).toContain("not a confirmed order");
  });

  it("includes imported product photographs in enquiries", () => {
    const imported = { ...product, displayImageKind: "product" as const, displayImage: "/images/catalogue/photo.webp" };
    expect(productEnquiry(imported, variant, "https://shop.example")).toContain("Photo: https://shop.example/images/catalogue/photo.webp");
  });
});
