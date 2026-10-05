import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("renders the offline learning shell", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Geo Companion" })).toBeInTheDocument();
    expect(screen.getByText(/offline-first geography learning/i)).toBeInTheDocument();
  });
});
