import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "../../src/ui/components/button";

describe("Button", () => {
  it("renders an accessible button", () => {
    render(<Button>保存</Button>);

    expect(screen.getByRole("button", { name: "保存" })).toBeEnabled();
  });
});
