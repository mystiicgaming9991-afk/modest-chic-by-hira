import { describe, expect, it } from "vitest";
import { isUnauthorizedStaffError } from "./staff-session";

describe("staff session error classification", () => {
  it("redirects only authentication failures to staff sign-in", () => {
    expect(isUnauthorizedStaffError(Object.assign(new Error("Expired session"), { status: 401 }))).toBe(true);
    expect(isUnauthorizedStaffError(Object.assign(new Error("Service unavailable"), { status: 503 }))).toBe(false);
    expect(isUnauthorizedStaffError(new TypeError("Failed to fetch"))).toBe(false);
  });
});
