import { afterEach, describe, expect, it, vi } from "vitest";
import { generateMetadata } from "./layout";

describe("collection page metadata", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("uses a published collection and excludes missing collections from indexing", async () => {
    vi.stubEnv("COMMERCE_API_URL", "https://commerce.example.test");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://modest.example.test");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [{
      slug: "new-arrivals", name: "New Arrivals", description: "Fresh styles for this season.",
    }] }), { status: 200 }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "new-arrivals" }) });

    expect(metadata.title).toBe("New Arrivals | Modest Chic");
    expect(metadata.description).toBe("Fresh styles for this season.");
    expect(metadata.alternates?.canonical).toBe("https://modest.example.test/collections/new-arrivals");

    vi.stubEnv("COMMERCE_API_URL", "");
    const unavailable = await generateMetadata({ params: Promise.resolve({ slug: "unknown-set" }) });
    expect(unavailable.robots).toEqual({ index: false, follow: false });
  });
});
