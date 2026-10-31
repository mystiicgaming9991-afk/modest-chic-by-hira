import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

describe("app response security headers", () => {
  it("applies safe browser defaults to every route", async () => {
    const rules = await nextConfig.headers?.();
    expect(rules).toHaveLength(1);
    expect(rules?.[0]?.source).toBe("/:path*");
    expect(Object.fromEntries((rules?.[0]?.headers ?? []).map(({ key, value }) => [key, value]))).toEqual({
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    });
  });
});
