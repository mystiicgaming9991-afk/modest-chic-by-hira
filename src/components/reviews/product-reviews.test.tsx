import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProductReviews } from "./product-reviews";

const firstPage = {
  review_count: 2,
  average_rating: 4.5,
  items: [{
    id: "review-1", rating: 5, title: "Lovely", body: "Soft fabric.",
    verified_purchase: true, created_at: "2026-10-25T10:00:00Z",
  }],
  next_cursor: "review-1",
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("product reviews", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows approved ratings and loads the next stable-cursor page", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => firstPage,
    } as Response).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        review_count: 2,
        average_rating: 4.5,
        items: [{
          id: "review-2", rating: 4, title: "Great", body: null,
          verified_purchase: true, created_at: "2026-10-24T10:00:00Z",
        }],
        next_cursor: null,
      }),
    } as Response);
    const user = userEvent.setup();
    render(<ProductReviews slug="linen-scarf" />);

    expect(await screen.findByText("Lovely")).toBeInTheDocument();
    expect(screen.getByText("2 reviews · 4.5 out of 5")).toBeInTheDocument();
    expect(screen.getByText("Verified purchase")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More reviews" }));

    expect(await screen.findByText("Great")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/commerce/catalog/products/linen-scarf/reviews?after=review-1",
      { cache: "no-store" },
    );
    expect(screen.queryByRole("button", { name: "More reviews" })).not.toBeInTheDocument();
  });

  it("drops old product reviews and ignores its pending page after the product changes", async () => {
    const oldNextPage = deferred<Response>();
    const fetchMock = vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(jsonResponse(firstPage))
      .mockReturnValueOnce(oldNextPage.promise)
      .mockResolvedValueOnce(jsonResponse({
        review_count: 1,
        average_rating: 5,
        items: [{
          id: "review-new", rating: 5, title: "New product review", body: null,
          verified_purchase: false, created_at: "2026-10-25T10:00:00Z",
        }],
        next_cursor: null,
      }));
    const user = userEvent.setup();
    const { rerender } = render(<ProductReviews slug="linen-scarf" />);

    expect(await screen.findByText("Lovely")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More reviews" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    rerender(<ProductReviews slug="cotton-scarf" />);

    expect(await screen.findByText("New product review")).toBeInTheDocument();
    expect(screen.queryByText("Lovely")).not.toBeInTheDocument();
    await act(async () => {
      oldNextPage.resolve(jsonResponse({
        review_count: 2,
        average_rating: 4,
        items: [{
          id: "review-stale", rating: 3, title: "Stale product page", body: null,
          verified_purchase: false, created_at: "2026-10-24T10:00:00Z",
        }],
        next_cursor: null,
      }));
      await oldNextPage.promise;
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    expect(screen.queryByText("Stale product page")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
