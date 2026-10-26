import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

// Component-level checks with a stubbed fetch. The full React -> FastAPI -> SQLite flow is
// covered by App.integration.test.tsx; these tests only pin client-side request behaviour.
const attribution = { source_title: "Original fixture", source_url: "https://creativecommons.org/publicdomain/zero/1.0/", creator: "Geo Companion contributors", license_name: "CC0-1.0", license_url: "https://creativecommons.org/publicdomain/zero/1.0/", attribution_text: "Original diagram.", accessed_on: "2026-10-14", reviewed_on: "2026-10-14", geographic_scope: "Synthetic classroom scene", rights_status: "cleared" };
const round = (id: string) => ({ round_id: id, asset_id: `${id}.svg`, asset_kind: "diagram", asset_attribution: attribution, asset_description: `Diagram ${id}` });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("only enables guesses that are two letters and retries without requesting another round", async () => {
    let nextCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/practice/rounds/next")) return json(round(`round-${++nextCalls}`));
      if (url.endsWith("/practice/rounds/round-1/answers")) return json({ round_id: "round-1", attempt_id: "a-1", is_correct: false, submission: { skipped: true, uncertain: false }, answer: { country_code: "ZZ", coordinate: null, answer_origin: "authored", explanation: "Authored teaching target: Zedland.", citations: [attribution] }, study_progress: null });
      return json({ detail: "Unexpected request" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("img", { name: "Diagram round-1" })).toBeInTheDocument();
    const guess = screen.getByLabelText(/Country-code guess/);
    fireEvent.change(guess, { target: { value: "1" } });
    expect(screen.getByRole("button", { name: "Submit guess" })).toBeDisabled();
    fireEvent.change(guess, { target: { value: "fr" } });
    expect(screen.getByRole("button", { name: "Submit guess" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText(/Zedland/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry same round" }));
    expect(screen.getByRole("img", { name: "Diagram round-1" })).toBeInTheDocument();
    expect(screen.queryByText(/Zedland/)).not.toBeInTheDocument();
    expect(nextCalls).toBe(1);
  });

  it("disables round actions while a submission is in flight so one click records one attempt", async () => {
    let answers = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/practice/rounds/next")) return json(round("round-1"));
      if (!String(input).endsWith("/answers")) return json({ active: null });
      answers += 1;
      return new Promise<Response>(() => {});
    }));
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Skip" }));
    expect(screen.getByRole("button", { name: "Skip" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(answers).toBe(1);
  });

  it("loads diagrams from the web app and photos from the local API", async () => {
    let nextCalls = 0;
    const photo = { round_id: "photo-ab12", asset_id: "ab12.jpg", asset_kind: "photo", asset_attribution: attribution, asset_description: "Street-level photo" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/practice/rounds/next")) return json(++nextCalls === 1 ? round("round-1") : photo);
      if (url.endsWith("/answers")) return json({ round_id: "round-1", attempt_id: "a-1", is_correct: false, submission: { skipped: true, uncertain: false }, answer: { country_code: "ZZ", coordinate: null, answer_origin: "authored", explanation: "Zedland.", citations: [attribution] }, study_progress: null });
      return json({ active: null });
    }));
    render(<App />);
    expect(await screen.findByRole("img", { name: "Diagram round-1" })).toHaveAttribute("src", "/starter-assets/round-1.svg");
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.click(await screen.findByRole("button", { name: "Next round" }));
    expect(await screen.findByRole("img", { name: "Street-level photo" })).toHaveAttribute("src", "/api/v1/assets/ab12.jpg");
    expect(screen.getByLabelText("Photo attribution")).toBeInTheDocument();
  });

  it("shows an unreachable local service as an error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to fetch");
  });
});
