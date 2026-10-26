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

  it("sends the chosen photo to the local API as raw bytes and shows the model's guess", async () => {
    const model = { model_id: "dummy-placeholder", version: "0.1.0", runtime: "dummy", is_placeholder: true, description: "Placeholder.", required_for_learning: false };
    const uploads: { type: string | null; body: unknown }[] = [];
    Object.assign(URL, { createObjectURL: () => "blob:preview", revokeObjectURL: () => {} });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/practice/rounds/next")) return json(round("round-1"));
      if (url.endsWith("/models")) return json({ active: model });
      if (url.endsWith("/photo-guesses")) {
        uploads.push({ type: new Headers(init?.headers).get("content-type"), body: init?.body });
        return json({ model, candidates: [{ country_code: "PT", confidence: 0.41 }, { country_code: "ES", confidence: 0.3 }, { country_code: "BR", confidence: 0.1 }], abstained: false, origin: "model_prediction" });
      }
      return json({ detail: "Unexpected request" }, 500);
    }));
    render(<App />);
    await screen.findByRole("img", { name: "Diagram round-1" });
    fireEvent.click(screen.getByRole("button", { name: "Your photo" }));
    const ask = screen.getByRole("button", { name: "Ask the model" });
    expect(ask).toBeDisabled();

    const photo = new File([new Uint8Array([0xff, 0xd8, 0xff])], "holiday.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText(/Photo \(JPEG/), { target: { files: [photo] } });
    expect(screen.getByRole("img", { name: "Your chosen photo" })).toHaveAttribute("src", "blob:preview");
    fireEvent.click(ask);

    const guess = await screen.findByLabelText("Model guess for your photo");
    expect(guess).toHaveTextContent("PT · 41%");
    expect(guess).toHaveTextContent("placeholder, not real inference");
    expect(uploads).toEqual([{ type: "image/jpeg", body: photo }]);
  });

  it("shows why a photo was refused", async () => {
    const model = { model_id: "dummy-placeholder", version: "0.1.0", runtime: "dummy", is_placeholder: true, description: "Placeholder.", required_for_learning: false };
    Object.assign(URL, { createObjectURL: () => "blob:preview", revokeObjectURL: () => {} });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/practice/rounds/next")) return json(round("round-1"));
      if (url.endsWith("/models")) return json({ active: model });
      return json({ detail: "This is one of the practice photos." }, 409);
    }));
    render(<App />);
    await screen.findByRole("img", { name: "Diagram round-1" });
    fireEvent.click(screen.getByRole("button", { name: "Your photo" }));
    fireEvent.change(screen.getByLabelText(/Photo \(JPEG/), { target: { files: [new File(["x"], "a.jpg", { type: "image/jpeg" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Ask the model" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("one of the practice photos");
    expect(screen.queryByLabelText("Model guess for your photo")).not.toBeInTheDocument();
  });

  it("shows an unreachable local service as an error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to fetch");
  });
});
