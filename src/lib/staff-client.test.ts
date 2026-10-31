import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { staffFetch, staffJson } from "./staff-client";

describe("staff request recovery", () => {
  let fakeFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fakeFetch = vi.fn();
    vi.stubGlobal("fetch", fakeFetch);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("returns a refresh outage instead of treating the old 401 as final", async () => {
    fakeFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "Refresh service unavailable." }), { status: 503 }));

    const response = await staffFetch("admin/orders");

    expect(response.status).toBe(503);
    expect(fakeFetch).toHaveBeenCalledTimes(2);
  });

  it("retains a real 401 when the refresh credential is rejected", async () => {
    fakeFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await staffFetch("admin/orders");

    expect(response.status).toBe(401);
    expect(fakeFetch).toHaveBeenCalledTimes(2);
  });

  it("shares one refresh request across concurrent unauthorized staff calls", async () => {
    let staffRequests = 0;
    fakeFetch.mockImplementation(async (url: string) => {
      if (url === "/api/staff/auth/refresh") return new Response(null, { status: 200 });
      staffRequests += 1;
      return new Response(null, { status: staffRequests <= 2 ? 401 : 200 });
    });

    const [first, second] = await Promise.all([
      staffFetch("admin/orders"),
      staffFetch("admin/customers"),
    ]);

    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    expect(fakeFetch.mock.calls.filter(([url]) => url === "/api/staff/auth/refresh")).toHaveLength(1);
    expect(fakeFetch).toHaveBeenCalledTimes(5);
  });

  it("keeps the HTTP status available to workspace error handling", async () => {
    fakeFetch.mockResolvedValueOnce(new Response(JSON.stringify({ message: "Service unavailable." }), { status: 503 }));

    await expect(staffJson("admin/orders")).rejects.toMatchObject({ status: 503 });
  });
});
