import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "mc_customer_session";

function secureRequest(request: NextRequest): boolean {
  const hostname = request.headers.get("host")?.split(":")[0];
  return request.headers.get("x-forwarded-proto") === "https"
    || request.nextUrl.protocol === "https:"
    || (process.env.NODE_ENV === "production" && hostname !== "localhost" && hostname !== "127.0.0.1");
}

async function forward(request: NextRequest, context: RouteContext<"/api/customer/[...path]">) {
  const { path } = await context.params;
  const endpoint = path.join("/");
  const methods: Record<string, string[]> = {
    "request-otp": ["POST"], "verify-otp": ["POST"], "me": ["GET"],
    "logout": ["POST"], "logout-others": ["POST"], "orders": ["GET"],
    "consents/marketing-email": ["GET", "POST"],
  };
  const claim = /^orders\/([0-9a-f-]{36})\/claim$/.exec(endpoint);
  const review = /^orders\/([0-9a-f-]{36})\/reviews$/.exec(endpoint);
  if (!(claim ? request.method === "POST" : review ? request.method === "POST" : methods[endpoint]?.includes(request.method))) {
    return NextResponse.json({ message: "Unknown account endpoint." }, { status: 404 });
  }
  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    let sameOrigin = false;
    try {
      const url = new URL(origin ?? "");
      sameOrigin = (url.protocol === "http:" || url.protocol === "https:") && url.host === request.headers.get("host");
    } catch { sameOrigin = false; }
    if (!sameOrigin) return NextResponse.json({ message: "Request origin is invalid." }, { status: 403 });
  }
  const base = process.env.COMMERCE_API_URL;
  if (!base) return NextResponse.json({ message: "Account service is unavailable." }, { status: 503 });
  const headers = new Headers();
  if (request.headers.has("content-type")) headers.set("Content-Type", request.headers.get("content-type")!);
  const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
  if (sessionToken) headers.set("X-Customer-Token", sessionToken);
  if (claim || review) {
    const orderToken = request.cookies.get(`mc_order_${(claim ?? review)![1].replaceAll("-", "")}`)?.value;
    if (orderToken) headers.set("X-Order-Token", orderToken);
  }
  try {
    const upstream = await fetch(new URL(`/api/v1/customer-auth/${endpoint}`, base), {
      method: request.method, headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (endpoint === "verify-otp" && upstream.ok) {
      const { session_token, ...identity } = await upstream.json() as { session_token: string; customer_id: string; email: string };
      const response = NextResponse.json(identity, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      response.cookies.set(SESSION_COOKIE, session_token, {
        httpOnly: true, sameSite: "lax", secure: secureRequest(request), path: "/api", maxAge: 60 * 60 * 24 * 30,
      });
      return response;
    }
    const response = new NextResponse(upstream.body, { status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" } });
    if (endpoint === "logout" && upstream.ok) response.cookies.set(SESSION_COOKIE, "", {
      httpOnly: true, sameSite: "lax", secure: secureRequest(request), path: "/api", maxAge: 0,
    });
    return response;
  } catch {
    return NextResponse.json({ message: "Account service is temporarily unavailable." }, { status: 503 });
  }
}

export { forward as GET, forward as POST };
