import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("completes a lesson quiz, displays its cited explanation, and records a grade", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Knowledge" }));
    fireEvent.click(await screen.findByRole("button", { name: "A warning" }));

    expect(await screen.findByText(/triangle is the warning shape/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    expect(await screen.findByText(/review scheduled/i)).toBeInTheDocument();
  });

  it("keeps a practice answer hidden until a learner skips, then permits report and retry", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Open Practice" }));
    expect(await screen.findByText(/original educational fixture/i)).toBeInTheDocument();
    expect(screen.queryByText(/verified answer: slovakia/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip / uncertain" }));
    expect(await screen.findByText(/verified answer: slovakia/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Report issue" }));
    expect(await screen.findByText(/report saved/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
