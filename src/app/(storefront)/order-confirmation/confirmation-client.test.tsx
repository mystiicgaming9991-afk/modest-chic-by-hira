import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmationClient } from "./confirmation-client";

describe("private order confirmation", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the customer-safe order progress timeline", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        order_number: "MC-20261025-0001",
        state: "PROCESSING",
        payment_state: "PENDING",
        total_minor: 125000,
        items: [],
        events: [
          { label: "Order placed", occurred_at: "2026-10-25T09:00:00Z" },
          { label: "Your order is being prepared", occurred_at: "2026-10-25T10:00:00Z" },
        ],
      }),
    } as Response);

    render(<ConfirmationClient orderId="11111111-1111-4111-8111-111111111111" />);

    expect(await screen.findByRole("heading", { name: "Order progress" })).toBeInTheDocument();
    expect(screen.getByText("Order placed")).toBeInTheDocument();
    expect(screen.getByText("Your order is being prepared")).toBeInTheDocument();
  });
});
