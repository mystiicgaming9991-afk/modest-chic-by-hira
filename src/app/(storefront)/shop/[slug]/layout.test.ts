import { afterEach, describe, expect, it, vi } from "vitest";
import { generateMetadata } from "./layout";

describe("product page metadata", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("uses the published product title, description, and configured canonical URL", async () => {
    vi.stubEnv("COMMERCE_API_URL", "https://commerce.example.test");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://modest.example.test");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      title: "Linen Blend Scarf",
      description: "Soft linen. Easy everyday drape.",
      primary_image: { object_key: "/images/linen-scarf.webp", alt_text: "Linen scarf" },
    }), { status: 200 }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "linen-scarf" }) });

    expect(metadata.title).toBe("Linen Blend Scarf | Modest Chic");
    expect(metadata.description).toBe("Soft linen. Easy everyday drape.");
    expect(metadata.alternates?.canonical).toBe("https://modest.example.test/shop/linen-scarf");
    expect(metadata.openGraph?.images).toEqual([{ url: "https://modest.example.test/images/linen-scarf.webp", alt: "Linen scarf" }]);
  });

  it("keeps a missing product page out of search results when catalog data is unavailable", async () => {
    vi.stubEnv("COMMERCE_API_URL", "");

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "unknown-product" }) });

    expect(metadata.title).toBe("Unknown Product | Modest Chic");
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
