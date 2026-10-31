import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewModerationPage from "./page";

const { staffJson, replace, router } = vi.hoisted(() => {
  const replace = vi.fn();
  return { staffJson: vi.fn(), replace, router: { replace } };
});

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({ staffJson }));

const review = {
  id: "11111111-1111-4111-8111-111111111111",
  product_title: "Rose scarf",
  order_number: "MC-20261025-0001",
  rating: 5,
  title: "Lovely",
  body: "Soft and comfortable.",
  created_at: "2026-10-25T10:00:00Z",
};

describe("review moderation workspace", () => {
  beforeEach(() => {
    staffJson.mockReset();
    replace.mockReset();
  });

  it("requires a reason and submits the selected moderation decision", async () => {
    let queueReads = 0;
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return { permission_keys: ["review.moderate"] };
      if (path === "admin/reviews?limit=100&offset=0") {
        queueReads += 1;
        return { items: queueReads === 1 ? [review] : [], total_count: 0, limit: 100, offset: 0 };
      }
      if (path.endsWith("/moderate")) return { id: review.id, status: "APPROVED" };
      throw new Error(`Unexpected request: ${path}`);
    });

    const user = userEvent.setup();
    render(<ReviewModerationPage />);

    expect(await screen.findByRole("heading", { name: "Rose scarf" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 3 characters");
    expect(staffJson.mock.calls.some(([path]) => String(path).endsWith("/moderate"))).toBe(false);

    await user.type(screen.getByLabelText("Moderation reason"), "Meets review policy");
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith(
      `admin/reviews/${review.id}/moderate`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ status: "APPROVED", reason: "Meets review policy" }),
      }),
    ));
    expect(await screen.findByRole("status")).toHaveTextContent("Review approved.");
  });

  it("does not load the moderation queue without permission", async () => {
    staffJson.mockResolvedValue({ permission_keys: ["order.read"] });

    render(<ReviewModerationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("does not have permission to moderate reviews");
    expect(staffJson).toHaveBeenCalledTimes(1);
  });

  it("ignores a late queue page after moderation refreshes the results", async () => {
    const nextReview = { ...review, id: "22222222-2222-4222-8222-222222222222", product_title: "Blue shawl" };
    let resolveOldPage!: (value: { items: typeof review[]; total_count: number; limit: number; offset: number }) => void;
    const oldPage = new Promise<{ items: typeof review[]; total_count: number; limit: number; offset: number }>((resolve) => { resolveOldPage = resolve; });
    let firstPageReads = 0;
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return { permission_keys: ["review.moderate"] };
      if (path === "admin/reviews?limit=100&offset=0") {
        firstPageReads += 1;
        return { items: firstPageReads === 1 ? [review] : [nextReview], total_count: firstPageReads === 1 ? 2 : 1, limit: 100, offset: 0 };
      }
      if (path === "admin/reviews?limit=100&offset=1") return oldPage;
      if (path === `admin/reviews/${review.id}/moderate`) return { id: review.id, status: "APPROVED" };
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<ReviewModerationPage />);

    await user.click(await screen.findByRole("button", { name: "Load more reviews" }));
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/reviews?limit=100&offset=1"));
    await user.type(await screen.findByLabelText("Moderation reason"), "Meets review policy");
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("heading", { name: "Blue shawl" })).toBeInTheDocument();

    await act(async () => {
      resolveOldPage({ items: [review], total_count: 2, limit: 100, offset: 1 });
      await oldPage;
    });
    expect(screen.getByRole("heading", { name: "Blue shawl" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Rose scarf" })).not.toBeInTheDocument();
  });
});
