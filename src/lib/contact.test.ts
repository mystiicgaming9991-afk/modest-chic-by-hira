import { describe, expect, it } from "vitest";
import { getContactChannels } from "./contact";

describe("public contact settings", () => {
  it("derives links from the configured public contact details", () => {
    expect(getContactChannels({ email: "modestchic00@gmail.com", instagramHandle: "modestchic.pk" })).toEqual({
      email: { label: "modestchic00@gmail.com", href: "mailto:modestchic00@gmail.com" },
      instagram: { label: "@modestchic.pk", href: "https://www.instagram.com/modestchic.pk/" },
    });
  });

  it("trims settings and safely encodes mailbox characters instead of creating query parameters", () => {
    const result = getContactChannels({ email: " hello+orders&help?desk@example.com ", instagramHandle: " new.store_2 " });
    expect(result.email).toEqual({ label: "hello+orders&help?desk@example.com", href: "mailto:hello%2Borders%26help%3Fdesk@example.com" });
    expect(result.instagram?.href).toBe("https://www.instagram.com/new.store_2/");
  });

  it("hides blank channels independently", () => {
    expect(getContactChannels({ email: " ", instagramHandle: "" })).toEqual({ email: null, instagram: null });
    expect(getContactChannels({ email: "", instagramHandle: "modestchic.pk" }).instagram).not.toBeNull();
    expect(getContactChannels({ email: "help@example.com", instagramHandle: "" }).email).not.toBeNull();
  });

  it.each([null, [], {}, { email: null, instagramHandle: "" }, { email: "", instagramHandle: 123 }])("rejects malformed configuration: %j", (config) => {
    expect(() => getContactChannels(config)).toThrow("Contact settings:");
  });

  it.each(["not-an-email", "hello@example", "mailto:hello@example.com", "hello@example.com?bcc=other@example.com", "hello@example.com\r\nBcc:other@example.com", "A Person <hello@example.com>", ".hello@example.com", "hello.@example.com", "hello..there@example.com"])("rejects an invalid email: %s", (email) => {
    expect(() => getContactChannels({ email, instagramHandle: "" })).toThrow("Contact settings: email");
  });

  it.each(["@modestchic.pk", "https://www.instagram.com/modestchic.pk", "../other", "store?next=other", ".store", "store.", "store..name", "a".repeat(31)])("rejects a handle that cannot form a profile URL: %s", (instagramHandle) => {
    expect(() => getContactChannels({ email: "", instagramHandle })).toThrow("Contact settings: instagramHandle");
  });
});
