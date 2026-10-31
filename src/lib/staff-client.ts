export interface StaffIdentity {
  id: string;
  email: string;
  name: string;
  permission_keys: string[];
  totp_enabled: boolean;
}

export interface StaffMember {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
  totp_enabled: boolean;
  last_login_at: string | null;
  updated_at: string;
}

const protectedPath = (path: string) => path === "auth/me" || path.startsWith("admin/")
  || ["auth/setup-totp", "auth/verify-totp", "auth/password/change"].includes(path);

let refreshRequest: Promise<Response> | null = null;

function refreshStaffSession(): Promise<Response> {
  if (refreshRequest) return refreshRequest;
  const refresh = () => fetch("/api/staff/auth/refresh", { method: "POST", cache: "no-store" });
  const request = typeof navigator !== "undefined" && navigator.locks
    ? Promise.resolve(navigator.locks.request("modest-chic-staff-refresh", refresh))
    : refresh();
  const sharedRequest = request.finally(() => { refreshRequest = null; });
  refreshRequest = sharedRequest;
  return sharedRequest;
}

export async function staffFetch(path: string, init?: RequestInit): Promise<Response> {
  const send = () => fetch(`/api/staff/${path}`, { ...init, cache: "no-store" });
  let response = await send();
  if (response.status === 401 && protectedPath(path)) {
    const refreshed = await refreshStaffSession();
    if (refreshed.ok) response = await send();
    else if (refreshed.status !== 401) response = refreshed;
  }
  return response;
}

export async function staffJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await staffFetch(path, init);
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  }
  const body = await response.json().catch(() => ({})) as { message?: string };
  const error = new Error(body.message ?? `Request failed (${response.status}).`);
  Object.assign(error, { status: response.status });
  throw error;
}

export function jsonBody(value: object): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) };
}
