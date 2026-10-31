import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PublicPolicy } from "./public-policy";

const { getMode, setMode } = vi.hoisted(() => {
  let mode = "preview";
  return {
    getMode: () => mode,
    setMode: (nextMode: string) => { mode = nextMode; },
  };
});

vi.mock("@/lib/context/catalog-context", () => ({
  useCatalog: () => ({ mode: getMode() }),
}));

describe("public policy display", () => {
  beforeEach(() => {
    setMode("preview");
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => vi.unstubAllGlobals());

  it("uses preview copy without requesting unapproved policy content", () => {
    render(<PublicPolicy type="shipping" preview="Shipping terms will be published before orders open." />);

    expect(screen.getByText("Shipping terms will be published before orders open.")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not show the previous policy while another policy loads", async () => {
    let resolveShipping!: (response: Response) => void;
    let resolveReturns!: (response: Response) => void;
    const shippingResponse = new Promise<Response>((resolve) => { resolveShipping = resolve; });
    const returnsResponse = new Promise<Response>((resolve) => { resolveReturns = resolve; });
    vi.mocked(fetch)
      .mockReturnValueOnce(shippingResponse)
      .mockReturnValueOnce(returnsResponse);
    setMode("live");

    const view = render(<PublicPolicy type="shipping" preview="Shipping preview." />);
    resolveShipping(new Response(JSON.stringify({ content: { delivery_window: "Shipping policy text" } })));
    expect(await screen.findByText("Shipping policy text")).toBeInTheDocument();

    view.rerender(<PublicPolicy type="returns" preview="Returns preview." />);
    expect(screen.queryByText("Shipping policy text")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading policy…");

    resolveReturns(new Response(JSON.stringify({ content: { return_window: "Returns policy text" } })));
    await waitFor(() => expect(screen.getByText("Returns policy text")).toBeInTheDocument());
    expect(fetch).toHaveBeenNthCalledWith(1, "/api/commerce/policies/shipping", { cache: "no-store" });
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/commerce/policies/returns", { cache: "no-store" });
  });
});
