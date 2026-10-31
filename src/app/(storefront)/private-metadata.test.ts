import { describe, expect, it } from "vitest";
import { metadata as account } from "./account/layout";
import { metadata as cart } from "./cart/layout";
import { metadata as wishlist } from "./wishlist/layout";

describe("private storefront page indexing", () => {
  it("keeps account, cart, and wishlist pages out of search indexes", () => {
    for (const metadata of [account, cart, wishlist]) {
      expect(metadata.robots).toEqual({ index: false, follow: false });
    }
  });
});
