import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContactPage from "@/app/(storefront)/contact/page";
import { Footer } from "./footer";

const config = vi.hoisted(() => ({ email: "", instagramHandle: "" }));
vi.mock("@/content/contact.json", () => ({ default: config }));
vi.mock("next/image", () => ({ default: () => <span /> }));

describe("contact page and footer", () => {
  beforeEach(() => {
    config.email = "help@example.com";
    config.instagramHandle = "example.store";
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_NUMBER", "923144660921");
  });

  const renderContacts = () => render(<><ContactPage /><Footer /></>);

  it("uses one configuration for the page and footer, with safe Instagram links", () => {
    renderContacts();
    const emailLinks = screen.getAllByRole("link", { name: /help@example.com/ });
    expect(emailLinks).toHaveLength(2);
    for (const link of emailLinks) expect(link).toHaveAttribute("href", "mailto:help@example.com");
    const instagramLinks = screen.getAllByRole("link", { name: /@example.store/ });
    expect(instagramLinks).toHaveLength(2);
    for (const link of instagramLinks) {
      expect(link).toHaveAttribute("href", "https://www.instagram.com/example.store/");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      expect(link).toHaveAccessibleName(/opens in a new tab/);
    }
    const whatsappLinks = screen.getAllByRole("link", { name: "Chat on WhatsApp" });
    expect(whatsappLinks).toHaveLength(2);
    for (const link of whatsappLinks) {
      const url = new URL(link.getAttribute("href")!);
      expect(url.pathname).toBe("/923144660921");
      expect(url.searchParams.get("text")).toContain("General enquiry");
    }
  });

  it("updates both locations from a changed configuration", () => {
    config.email = "new@example.com";
    config.instagramHandle = "new.handle";
    renderContacts();
    for (const link of screen.getAllByRole("link", { name: /new@example.com/ })) expect(link).toHaveAttribute("href", "mailto:new@example.com");
    expect(screen.getAllByRole("link", { name: /@new.handle/ })).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /help@example.com/ })).not.toBeInTheDocument();
  });

  it.each(["email", "instagramHandle"] as const)("hides a blank %s in both locations without hiding other channels", (field) => {
    config[field] = "";
    renderContacts();
    const hiddenLabel = field === "email" ? /help@example.com/ : /@example.store/;
    const visibleLabel = field === "email" ? /@example.store/ : /help@example.com/;
    expect(screen.queryByRole("link", { name: hiddenLabel })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: visibleLabel })).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Chat on WhatsApp" })).toHaveLength(2);
  });

  it("keeps WhatsApp in the footer when email and Instagram are blank", () => {
    config.email = "";
    config.instagramHandle = "";
    renderContacts();
    expect(screen.queryByRole("heading", { name: "Email us" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Find us on Instagram" })).not.toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Contact channels" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Chat on WhatsApp" })).toHaveLength(2);
  });

  it("hides the footer WhatsApp link when the configured number is unavailable", () => {
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_NUMBER", "");
    renderContacts();
    expect(screen.queryByRole("link", { name: "Chat on WhatsApp" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /help@example.com/ })).toHaveLength(2);
  });
});
