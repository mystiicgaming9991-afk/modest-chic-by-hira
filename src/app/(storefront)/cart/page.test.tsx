import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CartPage from "./page";
import { useCart } from "@/lib/context/cart-context";
import { useCatalog } from "@/lib/context/catalog-context";
import { useToast } from "@/lib/context/toast-context";
import { useWishlist } from "@/lib/context/wishlist-context";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/context/cart-context", () => ({ useCart: vi.fn() }));
vi.mock("@/lib/context/catalog-context", () => ({ useCatalog: vi.fn() }));
vi.mock("@/lib/context/toast-context", () => ({ useToast: vi.fn() }));
vi.mock("@/lib/context/wishlist-context", () => ({ useWishlist: vi.fn() }));

describe("cart quantity controls", () => {
  const updateQuantity = vi.fn(async () => true);

  beforeEach(() => {
    vi.mocked(useCatalog).mockReturnValue({ mode: "preview" } as ReturnType<typeof useCatalog>);
    vi.mocked(useWishlist).mockReturnValue({
      add: vi.fn(),
      isWishlisted: vi.fn(() => false),
    } as unknown as ReturnType<typeof useWishlist>);
    vi.mocked(useToast).mockReturnValue({
      toasts: [],
      addToast: vi.fn(),
      removeToast: vi.fn(),
    } as ReturnType<typeof useToast>);
    vi.mocked(useCart).mockReturnValue({
      items: [{ lineId: "premium-chiffon-hijab::warm-sand", quantity: 1 }],
      itemCount: 1,
      subtotal: 1850,
      updateQuantity,
      removeItem: vi.fn(async () => true),
      getAllLines: () => [{
        lineId: "premium-chiffon-hijab::warm-sand",
        product: { slug: "premium-chiffon-hijab", title: "Premium Chiffon Hijab", fabric: "Chiffon" },
        variant: { name: "Warm Sand", price: 1850, stock: 5, colorHex: "#D4C5B9" },
        quantity: 1,
        lineTotal: 1850,
      }],
      formatPrice: (amount: number) => `Rs. ${amount}`,
      loading: false,
      error: null,
      refreshCart: vi.fn(async () => undefined),
    } as unknown as ReturnType<typeof useCart>);
  });

  it("names quantity controls for assistive technology and updates the chosen line", async () => {
    const user = userEvent.setup();
    render(<CartPage />);

    expect(screen.getByRole("button", { name: "Decrease quantity of Premium Chiffon Hijab" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Increase quantity of Premium Chiffon Hijab" }));

    expect(updateQuantity).toHaveBeenCalledWith("premium-chiffon-hijab::warm-sand", 2);
  });
});

describe("WhatsApp ordering safeguards", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_NUMBER", "923001234567");
    vi.mocked(useCatalog).mockReturnValue({ mode: "live" } as ReturnType<typeof useCatalog>);
    vi.mocked(useWishlist).mockReturnValue({ add: vi.fn(), isWishlisted: vi.fn(() => false) } as unknown as ReturnType<typeof useWishlist>);
    vi.mocked(useToast).mockReturnValue({ addToast: vi.fn() } as unknown as ReturnType<typeof useToast>);
    vi.mocked(useCart).mockReturnValue({
      items: [{ lineId: "missing", quantity: 1 }], itemCount: 1, subtotal: 0,
      getAllLines: () => [{ lineId: "missing", product: undefined, variant: undefined, quantity: 1, lineTotal: 0 }],
      formatPrice: (amount: number) => `Rs. ${amount}`, loading: false, error: null,
      refreshCart: vi.fn(), removeItem: vi.fn(), updateQuantity: vi.fn(),
    } as unknown as ReturnType<typeof useCart>);
  });
  it("blocks a request when a cart item cannot be resolved", () => {
    render(<CartPage />);
    expect(screen.getByRole("alert")).toHaveTextContent("Some product details are unavailable");
    expect(screen.queryByRole("button", { name: "Order via WhatsApp" })).not.toBeInTheDocument();
    vi.unstubAllEnvs();
  });
});
