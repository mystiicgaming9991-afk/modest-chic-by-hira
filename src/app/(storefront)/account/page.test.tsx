import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AccountPage from "./page";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("customer marketing consent", () => {
  beforeEach(() => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/customer/me") {
        return new Response(JSON.stringify({ customer_id: "customer-1", email: "buyer@example.test" }), { status: 200 });
      }
      if (url === "/api/customer/orders") return new Response(JSON.stringify({ items: [] }), { status: 200 });
      if (url === "/api/customer/consents/marketing-email" && init?.method !== "POST") {
        return new Response(JSON.stringify({ consented: true, recorded_at: "2026-10-25T10:00:00Z" }), { status: 200 });
      }
      if (url === "/api/customer/consents/marketing-email" && init?.method === "POST") {
        return new Response(JSON.stringify({ consented: false, recorded_at: "2026-10-25T10:01:00Z" }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  it("lets the signed-in customer withdraw marketing email consent", async () => {
    const user = userEvent.setup();
    render(<AccountPage />);

    await user.click(await screen.findByRole("button", { name: "Unsubscribe from marketing emails" }));

    expect(await screen.findByText("No optional marketing email consent is active. This preference does not change order-related communication.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("You are unsubscribed from optional marketing emails."));
    expect(vi.mocked(fetch).mock.calls.some(([url, init]) => String(url).endsWith("consents/marketing-email") && init?.method === "POST")).toBe(true);
  });

  it("shows buyer-safe progress for linked account orders", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/customer/me") {
        return new Response(JSON.stringify({ customer_id: "customer-1", email: "buyer@example.test" }), { status: 200 });
      }
      if (url === "/api/customer/orders") return new Response(JSON.stringify({ items: [{
        order_id: "order-1", order_number: "MC-20261025-0001", state: "PROCESSING",
        total_minor: 125000, created_at: "2026-10-25T09:00:00Z",
        events: [{ label: "Your order is being prepared", occurred_at: "2026-10-25T10:00:00Z" }],
      }] }), { status: 200 });
      if (url === "/api/customer/consents/marketing-email") return new Response(JSON.stringify({ consented: false, recorded_at: null }), { status: 200 });
      throw new Error(`Unexpected request: ${url}`);
    }));
    const user = userEvent.setup();
    render(<AccountPage />);

    await user.click(await screen.findByText("Order progress"));

    expect(screen.getByText("Your order is being prepared")).toBeInTheDocument();
  });
});

describe("customer account recovery", () => {
  it("offers retry on an account-service failure instead of showing a sign-in form", async () => {
    let accountRequests = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) !== "/api/customer/me") throw new Error(`Unexpected request: ${String(input)}`);
      accountRequests += 1;
      if (accountRequests === 1) {
        return new Response(JSON.stringify({ message: "Account service is unavailable." }), { status: 503 });
      }
      return new Response(JSON.stringify({ message: "Sign in to continue." }), { status: 401 });
    }));

    const user = userEvent.setup();
    render(<AccountPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Account information is temporarily unavailable.");
    expect(screen.queryByRole("button", { name: "Email me a code" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry account" }));

    expect(await screen.findByRole("button", { name: "Email me a code" })).toBeInTheDocument();
    expect(accountRequests).toBe(2);
  });
});

describe("customer email sign-in", () => {
  it("requests a one-time code and loads the account after verification", async () => {
    let authenticated = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/customer/me") {
        return authenticated
          ? new Response(JSON.stringify({ customer_id: "customer-1", email: "buyer@example.test" }), { status: 200 })
          : new Response(JSON.stringify({ message: "Sign in to continue." }), { status: 401 });
      }
      if (url === "/api/customer/request-otp") {
        return new Response(JSON.stringify({ message: "If this address can receive mail, a sign-in code has been sent." }), { status: 200 });
      }
      if (url === "/api/customer/verify-otp") {
        authenticated = true;
        return new Response(JSON.stringify({ customer_id: "customer-1", email: "buyer@example.test" }), { status: 200 });
      }
      if (url === "/api/customer/orders") return new Response(JSON.stringify({ items: [] }), { status: 200 });
      if (url === "/api/customer/consents/marketing-email") {
        return new Response(JSON.stringify({ consented: false, recorded_at: null }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url} ${init?.method ?? "GET"}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AccountPage />);

    expect(await screen.findByText(/Orders can be discussed with us on WhatsApp/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email address"), "buyer@example.test");
    await user.click(screen.getByRole("button", { name: "Email me a code" }));
    expect(await screen.findByLabelText("Six-digit code")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Six-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("buyer@example.test")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/customer/request-otp", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/customer/verify-otp", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ email: "buyer@example.test", code: "123456" }),
    }));
  });
});
