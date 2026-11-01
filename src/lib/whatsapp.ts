import { formatPrice, type Product, type ProductVariant } from "@/lib/data";

export interface EnquiryLine {
  product: Product;
  variant: ProductVariant;
  quantity: number;
  lineTotal: number;
}

export function whatsappNumber(value: string | undefined): string | null {
  return value && /^[1-9]\d{7,14}$/.test(value) ? value : null;
}

export function whatsappLink(number: string, message?: string): string {
  return `https://wa.me/${number}${message ? `?text=${encodeURIComponent(message)}` : ""}`;
}

function siteOrigin(browserOrigin: string): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL;
  if (configured) {
    try {
      const url = new URL(configured);
      if (url.protocol === "https:" || url.protocol === "http:") return url.origin;
    } catch { /* Use the current storefront when the configured URL is invalid. */ }
  }
  return browserOrigin;
}

function productDetails(product: Product, variant: ProductVariant, origin: string): string[] {
  const base = siteOrigin(origin);
  const image = product.displayImage;
  // Do not describe placeholders or illustrated swatches as product photographs.
  const hasPhoto = (product.displayImageKind === "product" || product.displayImageKind === "brand") && image?.startsWith("/images/") && !image.endsWith("product-placeholder.svg");
  return [
    `${product.title} — ${variant.name}`,
    ...(variant.sku ? [`SKU: ${variant.sku}`] : []),
    ...(product.fabric ? [`Fabric: ${product.fabric}`] : []),
    ...(product.dimensions ? [`Dimensions: ${product.dimensions}`] : []),
    `Product: ${base}/shop/${encodeURIComponent(product.slug)}`,
    hasPhoto ? `Photo: ${base}${image}` : "Photo: not available yet",
  ];
}

const CONFIRMATION = "Please confirm availability, prices, delivery and payment. This request is not a confirmed order.";

export function contactEnquiry(): string {
  return "*Modest Chic | General enquiry*\nHello! I would like some help with your collection, delivery or an existing order.\n\nMy question: ";
}

export function productEnquiry(product: Product, variant: ProductVariant, origin: string, quantity = 1): string {
  const price = variant.salePrice ?? variant.price;
  return [
    "*Modest Chic | Product enquiry*",
    "Hello! I am interested in this item:",
    "",
    ...productDetails(product, variant, origin),
    `Quantity: ${quantity}`,
    `Displayed price: ${formatPrice(price)} each`,
    `Estimated item subtotal: ${formatPrice(price * quantity)}`,
    "",
    CONFIRMATION,
  ].join("\n");
}

export function cartEnquiry(lines: EnquiryLine[], subtotal: number, origin: string, format: (value: number) => string): string {
  const items = lines.map(({ product, variant, quantity, lineTotal }, index) => [
    `*Item ${index + 1}*`,
    ...productDetails(product, variant, origin),
    `Quantity: ${quantity} | Price: ${format(lineTotal / quantity)} each | Subtotal: ${format(lineTotal)}`,
  ].join("\n"));
  return [
    "*Modest Chic | Cart order request*",
    "Hello! I would like to order the following items:",
    "",
    items.join("\n\n"),
    "",
    `Total quantity: ${lines.reduce((sum, line) => sum + line.quantity, 0)}`,
    `Estimated subtotal: ${format(subtotal)}`,
    "Delivery charge and payment method: to be confirmed in chat.",
    "",
    CONFIRMATION,
  ].join("\n");
}
