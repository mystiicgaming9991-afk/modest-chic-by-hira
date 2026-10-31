import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Header } from "./header";

const { useCart, useWishlist, useCatalog } = vi.hoisted(() => ({
  useCart: vi.fn(),
  useWishlist: vi.fn(),
  useCatalog: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("next/image", () => ({
  default: ({ alt }: { alt?: string }) => <span role="img" aria-label={alt || "Brand image"} />,
}));
vi.mock("@/lib/context/cart-context", () => ({ useCart }));
vi.mock("@/lib/context/wishlist-context", () => ({ useWishlist }));
vi.mock("@/lib/context/catalog-context", () => ({ useCatalog }));

describe("mobile site navigation", () => {
  beforeEach(() => {
    useCart.mockReturnValue({ itemCount: 0 });
    useWishlist.mockReturnValue({ count: 0 });
    useCatalog.mockReturnValue({ mode: "preview", categories: [], collections: [] });
    document.body.style.overflow = "";
  });

  it("traps keyboard focus in the open menu and restores it on Escape", async () => {
    const user = userEvent.setup();
    render(<><Header /><main id="site-main" aria-hidden="false" /><footer id="site-footer" /></>);
    const trigger = screen.getByRole("button", { name: "Open menu" });
    document.body.style.overflow = "clip";

    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Site navigation" });
    expect(document.body.style.overflow).toBe("hidden");
    for (const id of ["site-announcement", "site-header", "site-main", "site-footer"]) {
      expect(document.getElementById(id)).toHaveAttribute("inert");
      expect(document.getElementById(id)).toHaveAttribute("aria-hidden", "true");
    }
    const closeButton = within(dialog).getByRole("button", { name: "Close menu" });
    expect(closeButton).toHaveFocus();

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(within(dialog).getByRole("link", { name: "FAQ" })).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(closeButton).toHaveFocus();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Site navigation" })).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe("clip");
    expect(document.getElementById("site-main")).not.toHaveAttribute("inert");
    expect(document.getElementById("site-main")).toHaveAttribute("aria-hidden", "false");
    document.body.style.overflow = "";
  });
});
