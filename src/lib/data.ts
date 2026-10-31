// ============================================================
// Mock Data for Modest Chic — Prototype
// In production, this comes from the API/PostgreSQL
// ============================================================

export interface ProductVariant {
  id: string;
  name: string;
  color: string;
  colorHex: string;
  sku: string;
  price: number; // in PKR
  salePrice?: number;
  stock: number;
}

export interface ImageCredit {
  creator: string;
  sourceUrl: string;
  license: string;
  licenseUrl: string;
}

export interface Product {
  id: string;
  slug: string;
  title: string;
  description: string;
  fabric: string;
  dimensions: string;
  care: string;
  category: string;
  categories?: string[];
  collections?: string[];
  tags: string[];
  variants: ProductVariant[];
  displayImage: string;
  displayImageAlt: string;
  displayImageKind: "brand" | "reference" | "illustration";
  displayImageNote: string;
  imageCredit?: ImageCredit;
  rating: number;
  reviewCount: number;
  isNew: boolean;
  isBestSeller: boolean;
  isFeatured: boolean;
}

export interface Collection {
  id: string;
  slug: string;
  title: string;
  description: string;
  image: string;
  productCount: number;
}

export interface Category {
  id: string;
  slug: string;
  title: string;
  description: string;
  image: string;
  productCount: number;
}

// Products data
export const products: Product[] = [
  {
    id: "p1",
    slug: "premium-chiffon-hijab",
    title: "Premium Chiffon Hijab",
    description: "Lightweight, flowy chiffon hijab with a luxurious drape. Perfect for everyday wear and special occasions. The semi-sheer fabric offers breathable comfort while maintaining full coverage.",
    fabric: "Premium Korean Chiffon",
    dimensions: "180cm × 70cm",
    care: "Hand wash cold. Hang dry. Iron on low heat. Do not bleach.",
    category: "hijabs",
    tags: ["chiffon", "everyday", "breathable"],
    displayImage: "/images/modest-chic-gift-edit.webp",
    displayImageAlt: "Modest Chic collection styling with six folded hijabs in different colors",
    displayImageKind: "brand",
    displayImageNote: "Collection photo · multiple shades shown",
    variants: [
      {
        id: "v1",
        name: "Warm Sand",
        color: "Warm Sand",
        colorHex: "#D4C5B9",
        sku: "PCF-WS-001",
        price: 1850,
        stock: 25,
      },
      {
        id: "v2",
        name: "Dusty Rose",
        color: "Dusty Rose",
        colorHex: "#C2A591",
        sku: "PCF-DR-001",
        price: 1850,
        stock: 18,
      },
      {
        id: "v3",
        name: "Terracotta",
        color: "Terracotta",
        colorHex: "#9C6656",
        sku: "PCF-TC-001",
        price: 1850,
        stock: 15,
      },
      {
        id: "v4",
        name: "Espresso",
        color: "Espresso",
        colorHex: "#2C1D17",
        sku: "PCF-ES-001",
        price: 1850,
        stock: 20,
      },
      {
        id: "v5",
        name: "Sage",
        color: "Sage",
        colorHex: "#8C836C",
        sku: "PCF-SG-001",
        price: 1850,
        salePrice: 1550,
        stock: 8,
      }
    ],
    rating: 4.8,
    reviewCount: 124,
    isNew: false,
    isBestSeller: true,
    isFeatured: true,
  },
  {
    id: "p2",
    slug: "modal-silk-blend",
    title: "Modal Silk Blend Hijab",
    description: "A sophisticated blend of modal and silk that offers an unparalleled soft touch and subtle sheen. Ideal for formal occasions and evening wear.",
    fabric: "Modal Silk Blend",
    dimensions: "190cm × 72cm",
    care: "Dry clean recommended. Hand wash cold if necessary. Steam iron. Store folded.",
    category: "hijabs",
    tags: ["modal", "silk", "luxury", "formal"],
    displayImage: "/images/catalog/modal-silk.webp",
    displayImageAlt: "Illustrative still life of a softly draped ivory modal silk hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual fabric and shade may differ",
    variants: [
      {
        id: "v6",
        name: "Ivory Cream",
        color: "Ivory Cream",
        colorHex: "#FDF8F4",
        sku: "MSB-IC-001",
        price: 2450,
        stock: 12,
      },
      {
        id: "v7",
        name: "Blush Pink",
        color: "Blush Pink",
        colorHex: "#E8D0CC",
        sku: "MSB-BP-001",
        price: 2450,
        stock: 10,
      },
      {
        id: "v8",
        name: "Charcoal Grey",
        color: "Charcoal Grey",
        colorHex: "#3D3D3D",
        sku: "MSB-CG-001",
        price: 2450,
        stock: 16,
      }
    ],
    rating: 4.9,
    reviewCount: 89,
    isNew: true,
    isBestSeller: false,
    isFeatured: true,
  },
  {
    id: "p3",
    slug: "jersey-essentials-hijab",
    title: "Jersey Essentials Hijab",
    description: "Butter-soft jersey fabric with a matte finish. No pins needed — the fabric holds its shape beautifully. Your go-to for busy mornings and all-day comfort.",
    fabric: "Premium Cotton Jersey",
    dimensions: "175cm × 65cm",
    care: "Machine wash gentle cycle. Tumble dry low. No iron needed. Do not bleach.",
    category: "hijabs",
    tags: ["jersey", "everyday", "no-pins", "comfort"],
    displayImage: "/images/catalog/jersey-essentials.webp",
    displayImageAlt: "Illustrative still life of a soft olive jersey hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual fabric and shade may differ",
    variants: [
      {
        id: "v9",
        name: "Warm Taupe",
        color: "Warm Taupe",
        colorHex: "#B5A092",
        sku: "JE-WT-001",
        price: 1650,
        stock: 30,
      },
      {
        id: "v10",
        name: "Dusty Olive",
        color: "Dusty Olive",
        colorHex: "#7A7A6A",
        sku: "JE-DO-001",
        price: 1650,
        stock: 22,
      },
      {
        id: "v11",
        name: "Deep Rust",
        color: "Deep Rust",
        colorHex: "#5D382A",
        sku: "JE-DR-001",
        price: 1650,
        salePrice: 1400,
        stock: 5,
      }
    ],
    rating: 4.7,
    reviewCount: 203,
    isNew: false,
    isBestSeller: true,
    isFeatured: false,
  },
  {
    id: "p4",
    slug: "georgette-printed-hijab",
    title: "Georgette Printed Hijab",
    description: "Delicate georgette with exclusive Modest Chic prints. Each piece features unique hand-drawn-inspired patterns that add character to any outfit.",
    fabric: "Premium Georgette",
    dimensions: "180cm × 72cm",
    care: "Hand wash cold separately. Line dry in shade. Iron on reverse at low heat.",
    category: "hijabs",
    tags: ["georgette", "printed", "exclusive", "limited"],
    displayImage: "/images/catalog/georgette-printed.webp",
    displayImageAlt: "Illustrative close-up of a softly draped botanical print georgette hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual print and shade may differ",
    variants: [
      {
        id: "v12",
        name: "Botanical Print",
        color: "Botanical",
        colorHex: "#8C836C",
        sku: "GP-BP-001",
        price: 2200,
        stock: 10,
      },
      {
        id: "v13",
        name: "Paisley Print",
        color: "Paisley",
        colorHex: "#9C6656",
        sku: "GP-PP-001",
        price: 2200,
        stock: 7,
      }
    ],
    rating: 4.6,
    reviewCount: 56,
    isNew: true,
    isBestSeller: false,
    isFeatured: true,
  },
  {
    id: "p5",
    slug: "crinkle-cotton-hijab",
    title: "Crinkle Cotton Hijab",
    description: "Naturally textured crinkle cotton that never needs ironing. Breathable, lightweight, and perfect for the Pakistani summer.",
    fabric: "100% Crinkle Cotton",
    dimensions: "175cm × 68cm",
    care: "Machine wash cold. Do not wring. Hang dry. No iron — the crinkle is natural!",
    category: "hijabs",
    tags: ["cotton", "summer", "breathable", "no-iron"],
    displayImage: "/images/catalog/crinkle-cotton.webp",
    displayImageAlt: "Illustrative still life of an airy off-white crinkle cotton hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual fabric and shade may differ",
    variants: [
      {
        id: "v14",
        name: "Off White",
        color: "Off White",
        colorHex: "#F5EDE6",
        sku: "CC-OW-001",
        price: 1550,
        stock: 35,
      },
      {
        id: "v15",
        name: "Sand Beige",
        color: "Sand Beige",
        colorHex: "#D4C5B9",
        sku: "CC-SB-001",
        price: 1550,
        stock: 28,
      },
      {
        id: "v16",
        name: "Soft Olive",
        color: "Soft Olive",
        colorHex: "#B0B090",
        sku: "CC-SO-001",
        price: 1550,
        stock: 0,
      }
    ],
    rating: 4.5,
    reviewCount: 167,
    isNew: false,
    isBestSeller: false,
    isFeatured: false,
  },
  {
    id: "p6",
    slug: "luxe-satin-hijab",
    title: "Luxe Satin Hijab",
    description: "Gleaming satin with a weighty, elegant fall. Designed for weddings, Eid celebrations, and moments that deserve extra sparkle.",
    fabric: "Premium Duchess Satin",
    dimensions: "190cm × 75cm",
    care: "Dry clean only. Store rolled to prevent creasing. Handle with care.",
    category: "hijabs",
    tags: ["satin", "luxury", "occasion", "bridal"],
    displayImage: "/images/catalog/luxe-satin.webp",
    displayImageAlt: "Illustrative close-up of champagne satin hijab folds",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual fabric and shade may differ",
    variants: [
      {
        id: "v17",
        name: "Champagne Gold",
        color: "Champagne Gold",
        colorHex: "#D4B896",
        sku: "LS-CG-001",
        price: 2850,
        stock: 8,
      },
      {
        id: "v18",
        name: "Rose Gold",
        color: "Rose Gold",
        colorHex: "#C4A095",
        sku: "LS-RG-001",
        price: 2850,
        stock: 6,
      },
      {
        id: "v19",
        name: "Midnight Navy",
        color: "Midnight Navy",
        colorHex: "#1B1B30",
        sku: "LS-MN-001",
        price: 2850,
        stock: 10,
      }
    ],
    rating: 5.0,
    reviewCount: 42,
    isNew: true,
    isBestSeller: false,
    isFeatured: false,
  },
  {
    id: "p7",
    slug: "bamboo-ribbed-hijab",
    title: "Bamboo Ribbed Hijab",
    description: "Eco-friendly bamboo fabric with a subtle ribbed texture. Naturally antibacterial and moisture-wicking — perfect for active days.",
    fabric: "Bamboo Viscose Blend",
    dimensions: "180cm × 70cm",
    care: "Machine wash cold. Lay flat to dry. Low iron if needed.",
    category: "hijabs",
    tags: ["bamboo", "eco", "active", "ribbed"],
    displayImage: "/images/catalog/bamboo-ribbed.webp",
    displayImageAlt: "Illustrative still life of a sage ribbed bamboo hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual fabric and shade may differ",
    variants: [
      {
        id: "v20",
        name: "Cream",
        color: "Cream",
        colorHex: "#FDF8F4",
        sku: "BR-CR-001",
        price: 1950,
        stock: 20,
      },
      {
        id: "v21",
        name: "Mushroom",
        color: "Mushroom",
        colorHex: "#B8A99A",
        sku: "BR-MU-001",
        price: 1950,
        stock: 14,
      }
    ],
    rating: 4.7,
    reviewCount: 78,
    isNew: false,
    isBestSeller: false,
    isFeatured: false,
  },
  {
    id: "p8",
    slug: "undercap-essentials",
    title: "Undercap Essentials Set",
    description: "Breathable cotton-spandex undercaps in a set of 3 neutral tones. Seamless construction with an adjustable fit for all-day security.",
    fabric: "Cotton Spandex Blend",
    dimensions: "One Size — Adjustable",
    care: "Machine wash warm. Tumble dry low. Do not bleach.",
    category: "accessories",
    tags: ["undercap", "essentials", "set"],
    displayImage: "/images/catalog/undercap-illustration.webp",
    displayImageAlt: "Illustrative flat lay of three neutral undercaps",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual set design may differ",
    variants: [
      {
        id: "v22",
        name: "Neutral Set (3 pcs)",
        color: "Neutral Set",
        colorHex: "#D4C5B9",
        sku: "UE-NS-001",
        price: 950,
        stock: 40,
      }
    ],
    rating: 4.8,
    reviewCount: 312,
    isNew: false,
    isBestSeller: true,
    isFeatured: true,
  },
  {
    id: "p9",
    slug: "signature-neutral-hijab",
    title: "Signature Neutral Hijab",
    description: "Our signature piece — the hijab that started it all. Available in our iconic Modest Chic neutral palette: Warm Sand, Dusty Rose, Olive, and Cream. The perfect everyday hijab with a buttery soft drape.",
    fabric: "Premium Soft Chiffon",
    dimensions: "180cm × 72cm",
    care: "Hand wash cold. Hang dry. Iron on low heat. Love and wear daily.",
    category: "hijabs",
    tags: ["signature", "neutral", "everyday", "iconic"],
    displayImage: "/images/modest-chic-color-edit.webp",
    displayImageAlt: "Modest Chic collection styling with folded hijabs and branded packaging",
    displayImageKind: "brand",
    displayImageNote: "Collection photo · multiple shades shown",
    variants: [
      {
        id: "v23",
        name: "Warm Sand",
        color: "Warm Sand",
        colorHex: "#D4C5B9",
        sku: "SN-WS-001",
        price: 1950,
        stock: 30,
      },
      {
        id: "v24",
        name: "Dusty Rose",
        color: "Dusty Rose",
        colorHex: "#AE9B92",
        sku: "SN-DR-001",
        price: 1950,
        stock: 22,
      },
      {
        id: "v25",
        name: "Smokey Olive",
        color: "Smokey Olive",
        colorHex: "#8C836C",
        sku: "SN-SO-001",
        price: 1950,
        salePrice: 1650,
        stock: 12,
      },
      {
        id: "v26",
        name: "Warm Cream",
        color: "Warm Cream",
        colorHex: "#E8E7E6",
        sku: "SN-WC-001",
        price: 1950,
        stock: 25,
      },
      {
        id: "v27",
        name: "Mauve Grey",
        color: "Mauve Grey",
        colorHex: "#A79F9A",
        sku: "SN-MG-001",
        price: 1950,
        stock: 18,
      },
      {
        id: "v28",
        name: "Deep Terracotta",
        color: "Deep Terracotta",
        colorHex: "#9C6656",
        sku: "SN-DT-001",
        price: 1950,
        stock: 15,
      }
    ],
    rating: 4.9,
    reviewCount: 256,
    isNew: false,
    isBestSeller: true,
    isFeatured: true,
  },
  {
    id: "p10",
    slug: "pleated-voile-hijab",
    title: "Pleated Voile Hijab",
    description: "A feather-light voile with fine pleats that add soft texture and help the drape stay graceful from morning to evening.",
    fabric: "Pleated Voile",
    dimensions: "180cm × 70cm",
    care: "Hand wash cold in a mesh bag. Do not wring. Hang dry and avoid ironing the pleats.",
    category: "hijabs",
    tags: ["voile", "pleated", "lightweight", "new-arrival"],
    displayImage: "/images/catalog/pleated-voile.webp",
    displayImageAlt: "Illustrative still life of a dusty rose micropleated voile hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual pleat and shade may differ",
    variants: [
      { id: "v29", name: "Dusty Rose", color: "Dusty Rose", colorHex: "#C79E9B", sku: "PV-DR-001", price: 1850, stock: 16 },
      { id: "v30", name: "Soft Sage", color: "Soft Sage", colorHex: "#9B9B83", sku: "PV-SS-001", price: 1850, stock: 14 },
      { id: "v31", name: "Warm Ivory", color: "Warm Ivory", colorHex: "#E8DED2", sku: "PV-WI-001", price: 1850, stock: 18 },
    ],
    rating: 4.8,
    reviewCount: 0,
    isNew: true,
    isBestSeller: false,
    isFeatured: true,
  },
  {
    id: "p11",
    slug: "linen-blend-summer-hijab",
    title: "Linen Blend Summer Hijab",
    description: "An airy linen blend with a relaxed, natural weave and an easy drape made for warm days and everyday styling.",
    fabric: "Linen Viscose Blend",
    dimensions: "180cm × 70cm",
    care: "Hand wash cold. Reshape while damp and line dry in shade. Low iron if desired.",
    category: "hijabs",
    tags: ["linen", "summer", "breathable", "new-arrival"],
    displayImage: "/images/catalog/linen-blend-summer.webp",
    displayImageAlt: "Illustrative still life of a natural sand linen blend hijab",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual weave and shade may differ",
    variants: [
      { id: "v32", name: "Natural Flax", color: "Natural Flax", colorHex: "#B9A48F", sku: "LB-NF-001", price: 1750, stock: 20 },
      { id: "v33", name: "Soft Sand", color: "Soft Sand", colorHex: "#D4C5B9", sku: "LB-SS-001", price: 1750, stock: 18 },
      { id: "v34", name: "Stone Grey", color: "Stone Grey", colorHex: "#A59D94", sku: "LB-SG-001", price: 1750, stock: 12 },
    ],
    rating: 4.7,
    reviewCount: 0,
    isNew: true,
    isBestSeller: false,
    isFeatured: true,
  },
  {
    id: "p12",
    slug: "hijab-magnet-duo",
    title: "Hijab Magnet Duo",
    description: "A smooth, pin-free way to secure your hijab. Each duo pairs two lightweight magnets with a refined warm metal edge.",
    fabric: "Smooth coated finish with metal edge",
    dimensions: "Set of 2 magnets",
    care: "Keep away from small children and sensitive electronics. Store magnets together when not in use.",
    category: "accessories",
    tags: ["magnets", "accessories", "no-pins", "new-arrival"],
    displayImage: "/images/catalog/hijab-magnet-duo.webp",
    displayImageAlt: "Illustrative pair of dusty rose and ivory hijab magnets on folded fabric",
    displayImageKind: "illustration",
    displayImageNote: "Illustrative image · actual finish and color may differ",
    variants: [
      { id: "v35", name: "Rose & Ivory", color: "Rose & Ivory", colorHex: "#C79E9B", sku: "HM-RI-001", price: 650, stock: 32 },
      { id: "v36", name: "Sand & Cream", color: "Sand & Cream", colorHex: "#D4C5B9", sku: "HM-SC-001", price: 650, stock: 28 },
    ],
    rating: 4.9,
    reviewCount: 0,
    isNew: true,
    isBestSeller: false,
    isFeatured: false,
  },
];

export const collections: Collection[] = [
  {
    id: "c1",
    slug: "new-arrivals",
    title: "New Arrivals",
    description: "The latest additions to our collection — fresh fabrics, new colors, and exclusive designs.",
    image: "/images/catalog/modal-silk.webp",
    productCount: 12,
  },
  {
    id: "c2",
    slug: "best-sellers",
    title: "Featured Pieces",
    description: "A curated selection of colours and fabrics to start your Modest Chic edit.",
    image: "/images/modest-chic-gift-edit.webp",
    productCount: 8,
  },
  {
    id: "c3",
    slug: "everyday-essentials",
    title: "Everyday Essentials",
    description: "Breathable, comfortable hijabs designed for daily wear — from work to errands to coffee dates.",
    image: "/images/catalog/jersey-essentials.webp",
    productCount: 15,
  },
  {
    id: "c4",
    slug: "luxe-occasion",
    title: "Luxe Occasion",
    description: "Elevated fabrics and finishes for weddings, Eid, and celebrations that deserve something special.",
    image: "/images/catalog/luxe-satin.webp",
    productCount: 6,
  },
  {
    id: "c5",
    slug: "signature-neutrals",
    title: "The Signature Collection",
    description: "Our iconic neutral palette — warm beiges, dusty roses, and earthy tones that define the Modest Chic aesthetic.",
    image: "/images/modest-chic-color-edit.webp",
    productCount: 18,
  },
];

export const categories: Category[] = [
  {
    id: "cat1",
    slug: "hijabs",
    title: "Hijabs",
    description: "Explore our complete range of premium hijabs in chiffon, modal, jersey, georgette, and more.",
    image: "/images/modest-chic-color-edit.webp",
    productCount: 28,
  },
  {
    id: "cat2",
    slug: "accessories",
    title: "Accessories",
    description: "Undercaps, hijab pins, magnets, and styling essentials to complete your modest look.",
    image: "/images/catalog/undercap-illustration.webp",
    productCount: 10,
  },
  {
    id: "cat3",
    slug: "sets",
    title: "Gift Sets",
    description: "Curated sets perfect for gifting — or treating yourself to a coordinated collection.",
    image: "/images/modest-chic-gift-edit.webp",
    productCount: 5,
  },
];

export const fabrics = ["Chiffon", "Modal", "Jersey", "Georgette", "Cotton", "Satin", "Bamboo", "Voile", "Linen"];

export const colorFamilies = [
  { name: "Nude & Beige", hex: "#D4C5B9" },
  { name: "Dusty Rose", hex: "#AE9B92" },
  { name: "Terracotta", hex: "#9C6656" },
  { name: "Deep Rust", hex: "#5D382A" },
  { name: "Olive & Sage", hex: "#8C836C" },
  { name: "Cream & White", hex: "#FDF8F4" },
  { name: "Mauve Grey", hex: "#A79F9A" },
];

export interface CartItem {
  variantId: string;
  quantity: number;
  productSlug: string;
}

export const formatPrice = (amount: number): string => {
  return `Rs. ${amount.toLocaleString('en-PK')}`;
};
