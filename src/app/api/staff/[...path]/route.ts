import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "mc_staff_access";
const REFRESH_COOKIE = "mc_staff_refresh";
const STAFF_COOKIE_PATH = "/api/staff";
const AUTH_ENDPOINTS = new Set([
  "auth/login", "auth/accept-invitation", "auth/refresh", "auth/logout",
  "auth/me", "auth/password/forgot", "auth/password/reset",
  "auth/password/change", "auth/setup-totp", "auth/verify-totp",
]);
const LIST_AND_CREATE_ENDPOINTS = new Set([
  "admin/coupons", "admin/catalog/products", "admin/catalog/categories",
  "admin/catalog/collections", "admin/catalog/tags",
]);
const READ_ONLY_ENDPOINTS = new Set([
  "admin/staff", "admin/customers", "admin/reviews", "admin/notifications/outbox",
  "admin/orders/cod/pending", "admin/orders/manual/options", "admin/analytics/dashboard",
  "admin/analytics/attribution", "admin/orders",
]);

function supportedMethods(endpoint: string): string[] | null {
  if (AUTH_ENDPOINTS.has(endpoint)) return endpoint === "auth/me" ? ["GET"] : ["POST"];
  if (LIST_AND_CREATE_ENDPOINTS.has(endpoint)) return ["GET", "POST"];
  if (READ_ONLY_ENDPOINTS.has(endpoint)) return ["GET"];
  if (endpoint === "admin/settings") return ["GET", "PUT"];
  if (endpoint === "admin/policies") return ["GET", "POST"];
  if (endpoint === "admin/staff/invitations" || endpoint === "admin/orders/manual") return ["POST"];
  if (endpoint === "admin/settings/secrets") return ["PUT"];
  if (endpoint === "admin/inventory/thresholds") return ["PATCH"];
  if (/^admin\/inventory\/(?:locations|variants|balances|movements|out-of-stock|low-stock)$/.test(endpoint)) return ["GET"];
  if (/^admin\/inventory\/(?:receive|adjust)$/.test(endpoint)) return ["POST"];
  if (/^admin\/coupons\/[0-9a-f-]{36}$/.test(endpoint)
    || /^admin\/catalog\/(?:products\/[0-9a-f-]{36}|variants\/[0-9a-f-]{36}|categories\/[0-9a-f-]{36}|collections\/[0-9a-f-]{36})$/.test(endpoint)) {
    return endpoint.startsWith("admin/catalog/products/") ? ["GET", "PATCH"] : ["PATCH"];
  }
  if (/^admin\/catalog\/products\/[0-9a-f-]{36}\/categories$/.test(endpoint)
    || /^admin\/catalog\/products\/[0-9a-f-]{36}\/tags$/.test(endpoint)
    || /^admin\/catalog\/collections\/[0-9a-f-]{36}\/products$/.test(endpoint)) {
    return ["GET", "PUT"];
  }
  if (/^admin\/catalog\/products\/[0-9a-f-]{36}\/media$/.test(endpoint)) return ["POST"];
  if (/^admin\/catalog\/products\/[0-9a-f-]{36}\/(?:variants|archive)$/.test(endpoint)) return ["POST"];
  if (/^admin\/customers\/[0-9a-f-]{36}\/orders$/.test(endpoint)) return ["GET"];
  if (/^admin\/customers\/[0-9a-f-]{36}\/consents\/marketing-email$/.test(endpoint)) return ["GET"];
  if (/^admin\/customers\/[0-9a-f-]{36}\/addresses$/.test(endpoint)) return ["GET", "POST"];
  if (/^admin\/customers\/[0-9a-f-]{36}\/addresses\/[0-9a-f-]{36}$/.test(endpoint)) return ["PATCH"];
  if (/^admin\/customers\/[0-9a-f-]{36}\/account-status$/.test(endpoint)
    || /^admin\/reviews\/[0-9a-f-]{36}\/moderate$/.test(endpoint)
    || /^admin\/staff\/[0-9a-f-]{36}\/suspend$/.test(endpoint)
    || /^admin\/staff\/[0-9a-f-]{36}\/activate$/.test(endpoint)
    || /^admin\/orders\/[0-9a-f-]{36}\/start-processing$/.test(endpoint)
    || /^admin\/orders\/[0-9a-f-]{36}\/shipments\/pack$/.test(endpoint)
    || /^admin\/orders\/[0-9a-f-]{36}\/handoff$/.test(endpoint)
    || /^admin\/orders\/[0-9a-f-]{36}\/cancel$/.test(endpoint)
    || /^admin\/orders\/cod\/[0-9a-f-]{36}\/(?:contact-attempts|confirm|decline)$/.test(endpoint)) return ["POST"];
  if (/^admin\/staff\/[0-9a-f-]{36}\/roles$/.test(endpoint)) return ["PUT"];
  if (/^admin\/orders\/[0-9a-f-]{36}$/.test(endpoint)) return ["GET"];
  return null;
}

function cookieValue(header: string | null, name: string): string | null {
  return header?.match(new RegExp(`(?:^|,\\s*)${name}=([^;]+)`))?.[1] ?? null;
}

function secureRequest(request: NextRequest): boolean {
  const hostname = request.headers.get("host")?.split(":")[0];
  return request.headers.get("x-forwarded-proto") === "https"
    || request.nextUrl.protocol === "https:"
    || (process.env.NODE_ENV === "production" && hostname !== "localhost" && hostname !== "127.0.0.1");
}

async function forward(request: NextRequest, context: RouteContext<"/api/staff/[...path]">) {
  const endpoint = (await context.params).path.join("/");
  const methods = supportedMethods(endpoint);
  if (!methods) return NextResponse.json({ message: "Unknown staff endpoint." }, { status: 404 });
  if (!methods.includes(request.method)) {
    return NextResponse.json(
      { message: "Method not allowed for this staff endpoint." },
      { status: 405, headers: { Allow: methods.join(", ") } },
    );
  }
  const base = process.env.COMMERCE_API_URL;
  if (!base) return NextResponse.json({ message: "Staff access is not configured." }, { status: 503 });

  let browserOrigin: string | null = null;
  if (request.method !== "GET") {
    browserOrigin = request.headers.get("origin");
    try {
      const url = new URL(browserOrigin ?? "");
      if (!["http:", "https:"].includes(url.protocol) || url.host !== request.headers.get("host")) {
        return NextResponse.json({ message: "Request origin is invalid." }, { status: 403 });
      }
    } catch {
      return NextResponse.json({ message: "Request origin is invalid." }, { status: 403 });
    }
  }

  const url = new URL(`/api/v1/${endpoint}`, base);
  url.search = request.nextUrl.search;
  const headers = new Headers();
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (request.headers.has("content-type")) headers.set("Content-Type", request.headers.get("content-type")!);
  if (request.method !== "GET") {
    try {
      const csrfResponse = await fetch(new URL("/api/v1/auth/csrf", base), {
        cache: "no-store", signal: AbortSignal.timeout(10000),
      });
      const csrf = cookieValue(csrfResponse.headers.get("set-cookie"), "mc_csrf");
      if (!csrfResponse.ok || !csrf) throw new Error("CSRF unavailable");
      headers.set("Origin", browserOrigin!);
      headers.set("X-CSRF-Token", csrf);
      headers.set("Cookie", `mc_csrf=${csrf}${refresh ? `; mc_staff_refresh=${refresh}` : ""}`);
    } catch {
      return NextResponse.json({ message: "Staff security service is unavailable. Retry." }, { status: 503 });
    }
  }

  try {
    const upstream = await fetch(url, {
      method: request.method, headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    const secure = secureRequest(request);
    if ((endpoint === "auth/login" || endpoint === "auth/refresh") && upstream.ok) {
      const session = await upstream.json() as {
        access_token: string; expires_in: number; auth_state: string;
        staff_user: { id: string; name: string; roles: string[] };
      };
      const refreshToken = cookieValue(upstream.headers.get("set-cookie"), REFRESH_COOKIE);
      if (!refreshToken) throw new Error("Missing refresh credential");
      const response = NextResponse.json({
        auth_state: session.auth_state, staff_user: session.staff_user,
      }, { headers: { "Cache-Control": "no-store" } });
      response.cookies.set(ACCESS_COOKIE, session.access_token, {
        httpOnly: true, sameSite: "strict", secure, path: STAFF_COOKIE_PATH,
        maxAge: session.expires_in,
      });
      response.cookies.set(REFRESH_COOKIE, refreshToken, {
        httpOnly: true, sameSite: "strict", secure, path: STAFF_COOKIE_PATH,
        maxAge: 60 * 60 * 24 * 7,
      });
      return response;
    }
    const response = new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
    if (endpoint === "auth/logout" || (endpoint === "auth/refresh" && upstream.status === 401)) {
      response.cookies.delete({ name: ACCESS_COOKIE, path: STAFF_COOKIE_PATH });
      response.cookies.delete({ name: REFRESH_COOKIE, path: STAFF_COOKIE_PATH });
    }
    return response;
  } catch {
    return NextResponse.json({ message: "Staff service is temporarily unavailable. Retry." }, { status: 503 });
  }
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH };
