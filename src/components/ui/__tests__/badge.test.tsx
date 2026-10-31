import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge variant="new">New</Badge>);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("renders new variant", () => {
    render(<Badge variant="new">New</Badge>);
    const el = screen.getByText("New");
    expect(el.className).toContain("inline-flex");
  });

  it("renders sale variant text", () => {
    render(<Badge variant="sale">Sale</Badge>);
    expect(screen.getByText("Sale")).toBeInTheDocument();
  });

  it("renders bestseller variant text", () => {
    render(<Badge variant="bestseller">Featured</Badge>);
    expect(screen.getByText("Featured")).toBeInTheDocument();
  });

  it("renders outOfStock variant", () => {
    render(<Badge variant="outOfStock">Sold Out</Badge>);
    expect(screen.getByText("Sold Out")).toBeInTheDocument();
  });

  it("renders default variant", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default")).toBeInTheDocument();
  });
});