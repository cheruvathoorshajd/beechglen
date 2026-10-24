import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { renderAt } from "../test/render";
import { Badge, ConfidenceBar, Field, Segmented, SpecLabel, Wordmark, nextIndex } from "./index";

describe("primitives", () => {
  it("wordmark reads NEXUS 911", () => {
    renderAt("/", <Wordmark to="/" />);
    expect(screen.getByRole("link", { name: "Nexus911 home" }).textContent).toBe("Nexus911");
  });

  it("badge always carries its word", () => {
    render(<Badge tone="critical">Critical</Badge>);
    const badge = screen.getByText("Critical");
    expect(badge.className).toContain("critical");
  });

  it("confidence bar prints share and sources so color is never the only signal", () => {
    render(<ConfidenceBar value={0.8333} sources={7} label="white" />);
    expect(screen.getByText("83% · 7 sources")).toBeTruthy();
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("83");
  });

  it("field wires the error to the input", () => {
    render(<Field label="Your name" id="name" error="Enter your name, or continue as a guest." />);
    const input = screen.getByLabelText("Your name");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe("name-err");
    expect(screen.getByText("Enter your name, or continue as a guest.").className).toBe("ferr");
  });

  it("spec label marks the key part", () => {
    const { container } = render(<SpecLabel k="Step 2 of 3" rest={["How to read it"]} />);
    expect(container.querySelector(".k")?.textContent).toBe("Step 2 of 3");
  });

  it("segmented control moves with arrow keys", () => {
    function Speed() {
      const [value, setValue] = useState<"5" | "10" | "20">("10");
      return (
        <Segmented
          label="Speed"
          value={value}
          onChange={setValue}
          options={[
            { value: "5", label: "5×" },
            { value: "10", label: "10×" },
            { value: "20", label: "20×" },
          ]}
        />
      );
    }
    render(<Speed />);
    fireEvent.keyDown(screen.getByRole("radiogroup"), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "20×" }).getAttribute("aria-checked")).toBe("true");
    expect(nextIndex("ArrowLeft", 0, 3)).toBe(2);
  });
});
