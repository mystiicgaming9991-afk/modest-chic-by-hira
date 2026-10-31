import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DELETE as commerceDelete,
  GET as commerceGet,
  PATCH as commercePatch,
  POST as commercePost,
} from "@/app/api/commerce/[...path]/route";
import { GET as customerGet, POST as customerPost } from "@/app/api/customer/[...path]/route";
import { GET as staffGet, PATCH as staffPatch, POST as staffPost, PUT as staffPut } from "@/app/api/staff/[...path]/route";

const API_BASE = "https://commerce.example.test";
const ORDER_ID = "123e4567-e89b-12d3-a456-426614174000";

function makeRequest(url: string, init: Omit<RequestInit, "signal"> = {}): NextRequest {
  return new NextRequest(url, {
    ...init,
    headers: {
      host: "shop.example.test",
      ...Object.fromEntries(new Headers(init.headers).entries()),
    },
  });
}

function makeContext(path: string[]) {
  return { params: Promise.resolve({ path }) } as never;
}

describe("frontend API proxies", () => {
  const fetchMock = vi.fn<typeof fetch>();
  const previousApiUrl = process.env.COMMERCE_API_URL;

  beforeEach(() => {
    process.env.COMMERCE_API_URL = API_BASE;
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (previousApiUrl === undefined) delete process.env.COMMERCE_API_URL;
    else process.env.COMMERCE_API_URL = previousApiUrl;
  });

  it("forwards the public product-review path and query through the commerce proxy", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    const request = makeRequest(
      "http://shop.example.test/api/commerce/catalog/products/linen-scarf/reviews?limit=20",
    );

    const response = await commerceGet(request, makeContext(["catalog", "products", "linen-scarf", "reviews"]));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
    const [target, options] = fetchMock.mock.calls[0];
    expect(String(target)).toBe(`${API_BASE}/api/v1/catalog/products/linen-scarf/reviews?limit=20`);
    expect(new Headers(options?.headers).get("x-guest-token")).toBeTruthy();
  });

  it("rejects cross-origin commerce mutations before forwarding them", async () => {
    const request = makeRequest("http://shop.example.test/api/commerce/checkout/quote", {
      method: "POST",
      headers: { origin: "https://attacker.example.test", "content-type": "application/json" },
      body: JSON.stringify({}),
    });

    const response = await commercePost(request, makeContext(["checkout", "quote"]));

    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects methods that the public API route does not support", async () => {
    const request = makeRequest("http://shop.example.test/api/commerce/policies/shipping", {
      method: "POST",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ content: "unexpected update" }),
    });

    const response = await commercePost(request, makeContext(["policies", "shipping"]));

    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("GET");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["GET", ["policies", "shipping"]],
    ["POST", ["cart", "items"]],
    ["PATCH", ["cart", "items", ORDER_ID]],
    ["DELETE", ["cart", "items", ORDER_ID]],
    ["POST", ["checkout", "quote"]],
    ["POST", ["checkout", "orders"]],
  ] as const)("forwards supported %s commerce method for %s", async (method, path) => {
    const endpoint = path.join("/");
    const orderResponse = {
      order_id: ORDER_ID,
      access_token: "private-order-token",
      order_number: "MC-TEST-0001",
      state: "pending",
      total_minor: 1250,
    };
    fetchMock.mockResolvedValue(new Response(JSON.stringify(
      endpoint === "checkout/orders" ? orderResponse : { items: [] },
    ), { status: 200 }));
    const request = makeRequest(`http://shop.example.test/api/commerce/${endpoint}`, {
      method,
      headers: method === "GET" ? {} : {
        origin: "http://shop.example.test",
        "content-type": "application/json",
      },
      body: method === "GET" ? undefined : JSON.stringify({}),
    });
    const handlers = {
      GET: commerceGet,
      POST: commercePost,
      PATCH: commercePatch,
      DELETE: commerceDelete,
    };

    const response = await handlers[method](request, makeContext([...path]));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][1]?.method).toBe(method);
  });

  it("keeps customer order credentials in the proxy when claiming an order", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ claimed: true }), { status: 200 }));
    const request = makeRequest(`http://shop.example.test/api/customer/orders/${ORDER_ID}/claim`, {
      method: "POST",
      headers: {
        origin: "http://shop.example.test",
        cookie: `mc_order_${ORDER_ID.replaceAll("-", "")}=private-order-token`,
        "content-type": "application/json",
      },
      body: JSON.stringify({}),
    });

    const response = await customerPost(request, makeContext(["orders", ORDER_ID, "claim"]));

    expect(response.status).toBe(200);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("x-order-token")).toBe("private-order-token");
  });

  it("exchanges a customer OTP for an HttpOnly session cookie", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      session_token: "customer-session-secret",
      customer_id: ORDER_ID,
      email: "buyer@example.test",
    }), { status: 200 }));
    const request = makeRequest("http://shop.example.test/api/customer/verify-otp", {
      method: "POST",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ email: "buyer@example.test", code: "123456" }),
    });

    const response = await customerPost(request, makeContext(["verify-otp"]));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ customer_id: ORDER_ID, email: "buyer@example.test" });
    expect(response.cookies.get("mc_customer_session")?.value).toBe("customer-session-secret");
    expect(response.cookies.get("mc_customer_session")?.httpOnly).toBe(true);
    expect(response.cookies.get("mc_customer_session")?.path).toBe("/api");
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${API_BASE}/api/v1/customer-auth/verify-otp`);
  });

  it("forwards the customer session cookie only as an upstream identity header", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ customer_id: ORDER_ID, email: "buyer@example.test" }), { status: 200 }));
    const request = makeRequest("http://shop.example.test/api/customer/me", {
      headers: { cookie: "mc_customer_session=customer-session-secret" },
    });

    const response = await customerGet(request, makeContext(["me"]));

    expect(response.status).toBe(200);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("x-customer-token")).toBe("customer-session-secret");
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has("cookie")).toBe(false);
  });

  it("forwards authorized staff inventory reads with the staff access cookie", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    const request = makeRequest("http://shop.example.test/api/staff/admin/inventory/low-stock", {
      headers: { cookie: "mc_staff_access=staff-access-token" },
    });

    const response = await staffGet(request, makeContext(["admin", "inventory", "low-stock"]));

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${API_BASE}/api/v1/admin/inventory/low-stock`);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("authorization")).toBe("Bearer staff-access-token");
  });

  it("keeps the staff directory read-only", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const request = makeRequest("http://shop.example.test/api/staff/admin/staff", {
      headers: { cookie: "mc_staff_access=staff-access-token" },
    });

    const response = await staffGet(request, makeContext(["admin", "staff"]));

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${API_BASE}/api/v1/admin/staff`);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("GET");
  });

  it("forwards permitted staff reads and writes for saved customer addresses", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: "address-1" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "address-2" }), { status: 201 }));

    const getRequest = makeRequest(`http://shop.example.test/api/staff/admin/customers/${ORDER_ID}/addresses`, {
      headers: { cookie: "mc_staff_access=staff-access-token" },
    });
    const getResponse = await staffGet(getRequest, makeContext(["admin", "customers", ORDER_ID, "addresses"]));

    expect(getResponse.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${API_BASE}/api/v1/admin/customers/${ORDER_ID}/addresses`);

    const postRequest = makeRequest(`http://shop.example.test/api/staff/admin/customers/${ORDER_ID}/addresses`, {
      method: "POST",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ line1: "12 Example Road", city: "Karachi" }),
    });
    const postResponse = await staffPost(postRequest, makeContext(["admin", "customers", ORDER_ID, "addresses"]));

    expect(postResponse.status).toBe(201);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const forwardedHeaders = new Headers(fetchMock.mock.calls[2][1]?.headers);
    expect(forwardedHeaders.get("origin")).toBe("http://shop.example.test");
    expect(forwardedHeaders.get("x-csrf-token")).toBe("csrf-proof");
  });

  it("forwards existing product media attachment through the staff proxy", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "media-1" }), { status: 201 }));
    const endpoint = `admin/catalog/products/${ORDER_ID}/media`;
    const request = makeRequest(`http://shop.example.test/api/staff/${endpoint}`, {
      method: "POST",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ object_key: "products/demo/front.webp", media_type: "image/webp" }),
    });

    const response = await staffPost(request, makeContext(endpoint.split("/")));

    expect(response.status).toBe(201);
    expect(String(fetchMock.mock.calls[1][0])).toBe(`${API_BASE}/api/v1/${endpoint}`);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
  });

  it("forwards version-checked saved-address edits through the staff proxy", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "address-1" }), { status: 200 }));
    const endpoint = `admin/customers/${ORDER_ID}/addresses/${ORDER_ID}`;
    const request = makeRequest(`http://shop.example.test/api/staff/${endpoint}`, {
      method: "PATCH",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ expected_updated_at: "2026-10-25T10:00:00+00:00" }),
    });

    const response = await staffPatch(request, makeContext(endpoint.split("/")));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1][0])).toBe(`${API_BASE}/api/v1/${endpoint}`);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PATCH");
  });

  it("forwards current customer consent as a read-only staff resource", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ consented: false }), { status: 200 }));
    const endpoint = `admin/customers/${ORDER_ID}/consents/marketing-email`;
    const request = makeRequest(`http://shop.example.test/api/staff/${endpoint}`, {
      headers: { cookie: "mc_staff_access=staff-access-token" },
    });

    const response = await staffGet(request, makeContext(endpoint.split("/")));

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${API_BASE}/api/v1/${endpoint}`);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("GET");
  });

  it("forwards same-origin staff writes with API-issued CSRF proof", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ saved: true }), { status: 200 }));
    const request = makeRequest("http://shop.example.test/api/staff/admin/settings", {
      method: "PUT",
      headers: {
        origin: "http://shop.example.test",
        cookie: "mc_staff_access=staff-access-token; mc_staff_refresh=refresh-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({ key: "store.name", value: "Modest Chic", version: 1 }),
    });

    const response = await staffPut(request, makeContext(["admin", "settings"]));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const forwardedHeaders = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(forwardedHeaders.get("origin")).toBe("http://shop.example.test");
    expect(forwardedHeaders.get("x-csrf-token")).toBe("csrf-proof");
    expect(forwardedHeaders.get("cookie")).toBe("mc_csrf=csrf-proof; mc_staff_refresh=refresh-token");
  });

  it("rejects a write method on a read-only staff endpoint", async () => {
    const request = makeRequest("http://shop.example.test/api/staff/admin/inventory/balances", {
      method: "POST",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ unexpected: true }),
    });

    const response = await staffPost(request, makeContext(["admin", "inventory", "balances"]));

    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("GET");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["GET", ["admin", "settings", "secrets", "mailer.password"]],
    ["POST", ["admin", "customers", ORDER_ID, "consents"]],
  ] as const)("keeps unsupported staff operation %s %s outside the browser proxy", async (method, path) => {
    const request = makeRequest(`http://shop.example.test/api/staff/${path.join("/")}`, {
      method,
      headers: method === "GET" ? {} : {
        origin: "http://shop.example.test",
        "content-type": "application/json",
      },
      body: method === "GET" ? undefined : JSON.stringify({ consented: true }),
    });
    const handlers = { GET: staffGet, POST: staffPost };

    const response = await handlers[method](request, makeContext([...path]));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards staff role updates with the API's PUT contract", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ updated: true }), { status: 200 }));
    const request = makeRequest(`http://shop.example.test/api/staff/admin/staff/${ORDER_ID}/roles`, {
      method: "PUT",
      headers: {
        origin: "http://shop.example.test",
        cookie: "mc_staff_access=staff-access-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({ role_keys: ["warehouse"], expected_updated_at: "2026-10-25T00:00:00Z" }),
    });

    const response = await staffPut(request, makeContext(["admin", "staff", ORDER_ID, "roles"]));

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(`${API_BASE}/api/v1/admin/staff/${ORDER_ID}/roles`);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PUT");
  });

  it.each([
    `admin/catalog/collections/${ORDER_ID}/products`,
    `admin/catalog/products/${ORDER_ID}/categories`,
    `admin/catalog/products/${ORDER_ID}/tags`,
  ])("forwards catalog membership replacements with PUT: %s", async (endpoint) => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, {
        status: 200,
        headers: { "set-cookie": "mc_csrf=csrf-proof; Path=/; SameSite=Lax" },
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const request = makeRequest(`http://shop.example.test/api/staff/${endpoint}`, {
      method: "PUT",
      headers: { origin: "http://shop.example.test", "content-type": "application/json" },
      body: JSON.stringify({ expected_updated_at: "2026-10-25T00:00:00Z" }),
    });

    const response = await staffPut(request, makeContext(endpoint.split("/")));

    expect(response.status).toBe(204);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1][0])).toBe(`${API_BASE}/api/v1/${endpoint}`);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PUT");
  });

  it("does not expose unimplemented staff workflow paths through the proxy", async () => {
    const request = makeRequest("http://shop.example.test/api/staff/admin/refunds");

    const response = await staffGet(request, makeContext(["admin", "refunds"]));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
