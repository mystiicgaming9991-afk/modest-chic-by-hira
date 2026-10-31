import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const GUEST_COOKIE = "mc_guest";
const READ_ONLY_ENDPOINTS = new Set(["cart", "checkout/options"]);

function secureRequest(request: NextRequest): boolean {
  const hostname = request.headers.get("host")?.split(":")[0];
  return request.headers.get("x-forwarded-proto") === "https"
    || request.nextUrl.protocol === "https:"
    || (process.env.NODE_ENV === "production" && hostname !== "localhost" && hostname !== "127.0.0.1");
}

async function forward(request: NextRequest, context: RouteContext<"/api/commerce/[...path]">) {
  const { path } = await context.params;
  const endpoint = path.join("/");
  if (!/^(catalog\/(products(?:\/[^/]+)?(?:\/reviews)?|categories|collections|search)|cart(?:\/items(?:\/[0-9a-f-]{36})?)?|checkout\/(options|quote|orders)|orders\/[0-9a-f-]{36}|policies\/(shipping|returns))$/.test(endpoint)) {
    return NextResponse.json({ message: "Unknown commerce endpoint." }, { status: 404 });
  }

  const allowedMethods = READ_ONLY_ENDPOINTS.has(endpoint)
    || endpoint.startsWith("catalog/")
    || endpoint.startsWith("orders/")
    || endpoint.startsWith("policies/")
    ? ["GET"]
    : endpoint === "cart/items"
      ? ["POST"]
      : /^cart\/items\/[0-9a-f-]{36}$/.test(endpoint)
        ? ["PATCH", "DELETE"]
        : endpoint === "checkout/quote" || endpoint === "checkout/orders"
          ? ["POST"]
          : [];
  if (!allowedMethods.includes(request.method)) {
    return NextResponse.json(
      { message: "Method not allowed for this commerce endpoint." },
      { status: 405, headers: { Allow: allowedMethods.join(", ") } },
    );
  }

  const base = process.env.COMMERCE_API_URL;
  if (!base) {
    if (request.method === "GET" && endpoint.startsWith("catalog/")) {
      return NextResponse.json({ preview: true, items: [] }, { status: 200 });
    }
    return NextResponse.json({ code: "COMMERCE_UNAVAILABLE", message: "Ordering is not configured." }, { status: 503 });
  }

  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    let sameOrigin = false;
    try {
      const url = new URL(origin ?? "");
      sameOrigin = (url.protocol === "http:" || url.protocol === "https:")
        && url.host === request.headers.get("host");
    } catch {
      sameOrigin = false;
    }
    if (!sameOrigin) {
      return NextResponse.json({ message: "Request origin is invalid." }, { status: 403 });
    }
  }

  const guest = request.cookies.get(GUEST_COOKIE)?.value ?? randomBytes(32).toString("hex");
  const url = new URL(`/api/v1/${endpoint}`, base);
  url.search = request.nextUrl.search;
  const headers = new Headers({ "X-Guest-Token": guest });
  if (endpoint === "checkout/orders" || endpoint === "checkout/quote") {
    const customerToken = request.cookies.get("mc_customer_session")?.value;
    if (customerToken) headers.set("X-Customer-Token", customerToken);
  }
  if (endpoint.startsWith("orders/")) {
    const orderId = endpoint.slice("orders/".length).replaceAll("-", "");
    const orderToken = request.cookies.get(`mc_order_${orderId}`)?.value;
    if (orderToken) headers.set("X-Order-Token", orderToken);
  }
  if (request.headers.has("content-type")) headers.set("Content-Type", request.headers.get("content-type")!);
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (endpoint === "checkout/orders" && upstream.ok) {
      const order = await upstream.json() as { order_id: string; access_token: string; order_number: string; state: string; total_minor: number };
      const { access_token, ...publicOrder } = order;
      const response = NextResponse.json(publicOrder, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      response.cookies.set(`mc_order_${order.order_id.replaceAll("-", "")}`, access_token, {
        httpOnly: true, sameSite: "lax", secure: secureRequest(request),
        path: "/api", maxAge: 60 * 60 * 24 * 90,
      });
      response.cookies.set(GUEST_COOKIE, guest, {
        httpOnly: true, sameSite: "lax", secure: secureRequest(request),
        path: "/", maxAge: 60 * 60 * 24 * 7,
      });
      return response;
    }
    const response = new NextResponse(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
    response.cookies.set(GUEST_COOKIE, guest, {
      httpOnly: true,
      sameSite: "lax",
      secure: secureRequest(request),
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
    });
    return response;
  } catch {
    return NextResponse.json({ code: "COMMERCE_UNAVAILABLE", message: "The store is temporarily unavailable. Please retry." }, { status: 503 });
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
