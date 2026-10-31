import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CheckoutPage from "./page";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/context/catalog-context", () => ({ useCatalog: () => ({ mode: "live" }) }));
vi.mock("@/lib/context/cart-context", () => ({
  useCart: () => ({
    subtotal: 0,
    getAllLines: () => [],
    formatPrice: (amount: number) => `PKR ${amount}`,
    refreshCart: vi.fn(),
  }),
}));

const recoveryKey = "mc_checkout_recovery_v1";
const checkoutId = "retryable-checkout-key-123456";

function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("checkout recovery", () => {
  beforeEach(() => {
    sessionStorage.clear();
    push.mockReset();
  });

  it("restores and retries the same idempotent order after a lost response", async () => {
    sessionStorage.setItem(recoveryKey, JSON.stringify({
      version: 1,
      saved_at: Date.now(),
      quote: {
        cart_version: 4,
        subtotal_minor: 250000,
        shipping_charge_minor: 0,
        discount_minor: 0,
        total_minor: 250000,
        policy_version_ids: {
          checkout_bundle: "11111111-1111-4111-8111-111111111111",
          shipping: "22222222-2222-4222-8222-222222222222",
          returns: "33333333-3333-4333-8333-333333333333",
        },
        policies: {
          checkout_bundle: { policy_version_id: "11111111-1111-4111-8111-111111111111", version: 1, content: { checkout: "Approved terms" } },
          shipping: { policy_version_id: "22222222-2222-4222-8222-222222222222", version: 1, content: { shipping: "Approved shipping" } },
          returns: { policy_version_id: "33333333-3333-4333-8333-333333333333", version: 1, content: { returns: "Approved returns" } },
        },
        idempotency_key: checkoutId,
        applied_coupon: null,
        items: [{ product_title: "Premium Hijab", variant_name: "Rose", quantity: 1, line_total_minor: 250000 }],
      },
      form_data: {
        name: "Ayesha Khan",
        phone: "03001234567",
        email: "ayesha@example.com",
        address: "12 Example Road",
        area: "Clifton",
        city: "Karachi",
        postalCode: "75600",
        deliveryNotes: "Call on arrival",
        fulfillmentMethod: "delivery",
        paymentMethod: "cod",
      },
      accepted_policy: true,
      coupon_code: "",
    }));

    const submittedIds: string[] = [];
    const submittedPolicyVersions: unknown[] = [];
    let attempts = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/checkout/options")) {
        return response({ delivery_cities: ["Karachi"], pickup_cities: [], delivery_fee_minor: 25000, payment_methods: ["COD"] });
      }
      attempts += 1;
      const requestBody = JSON.parse(String(init?.body));
      submittedIds.push(requestBody.checkout_id as string);
      submittedPolicyVersions.push(requestBody.policy_version_ids);
      if (attempts === 1) return response({ message: "The response was interrupted." }, 503);
      return response({ order_id: "22222222-2222-4222-8222-222222222222" }, 201);
    }));

    const user = userEvent.setup();
    const { unmount } = render(<CheckoutPage />);
    expect(await screen.findByText("Checkout attempt restored")).toBeInTheDocument();
    expect(screen.getByText(/Approved shipping/)).toBeInTheDocument();
    expect(screen.getByText(/Approved returns/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Place COD Order" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The response was interrupted.");
    expect(JSON.parse(sessionStorage.getItem(recoveryKey) ?? "{}").quote.idempotency_key).toBe(checkoutId);

    unmount();
    render(<CheckoutPage />);
    expect(await screen.findByText("Checkout attempt restored")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Place COD Order" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/order-confirmation?order=22222222-2222-4222-8222-222222222222"));
    expect(submittedIds).toEqual([checkoutId, checkoutId]);
    expect(submittedPolicyVersions).toEqual([
      {
        checkout_bundle: "11111111-1111-4111-8111-111111111111",
        shipping: "22222222-2222-4222-8222-222222222222",
        returns: "33333333-3333-4333-8333-333333333333",
      },
      {
        checkout_bundle: "11111111-1111-4111-8111-111111111111",
        shipping: "22222222-2222-4222-8222-222222222222",
        returns: "33333333-3333-4333-8333-333333333333",
      },
    ]);
    expect(sessionStorage.getItem(recoveryKey)).toBeNull();
  });
});

describe("checkout form accessibility", () => {
  it("associates the visible contact and delivery labels with their controls", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({
      delivery_cities: ["Karachi"],
      pickup_cities: [],
      delivery_fee_minor: 25000,
      payment_methods: ["COD"],
    })));

    render(<CheckoutPage />);

    expect(await screen.findByLabelText(/Full Name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Phone Number/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Address/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Area/)).toBeInTheDocument();
    expect(screen.getByLabelText("City *")).toBeInTheDocument();
    expect(screen.getByLabelText(/Delivery Notes/)).toBeInTheDocument();
  });
});
