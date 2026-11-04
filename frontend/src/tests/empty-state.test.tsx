import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/ui/Card";

describe("empty state", () => {
  it("renders honest copy", () => {
    render(<EmptyState title="No observations yet" body="Import a labeled air-quality CSV." />);
    expect(screen.getByText("No observations yet")).toBeInTheDocument();
  });
});
