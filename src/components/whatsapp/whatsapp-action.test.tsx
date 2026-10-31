import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WhatsAppAction } from "./whatsapp-action";

afterEach(() => vi.unstubAllEnvs());

describe("WhatsApp action", () => {
  it("shows unavailable when no number is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_NUMBER", "");
    render(<WhatsAppAction label="Chat" message={() => "Hello"} />);
    expect(screen.getByText(/contact is currently unavailable/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Chat" })).not.toBeInTheDocument();
  });

  it("keeps the entire long message available with a separate chat link", async () => {
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_NUMBER", "923001234567");
    const message = "A & ".repeat(1000) + "last item";
    render(<WhatsAppAction label="Order via WhatsApp" message={() => message} />);
    await userEvent.click(screen.getByRole("link", { name: "Order via WhatsApp" }));
    expect(screen.getByLabelText("Complete message")).toHaveValue(message);
    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toHaveAttribute("href", "https://wa.me/923001234567");
  });
});
