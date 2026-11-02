import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RaceMode } from "./Race";

const attribution = { source_title: "OSV-5M", source_url: "https://huggingface.co/datasets/osv5m/osv5m", creator: "OSV-5M contributors", license_name: "CC-BY-SA-4.0", license_url: "https://creativecommons.org/licenses/by-sa/4.0/", attribution_text: "Photo from OSV-5M.", accessed_on: "2026-10-26", reviewed_on: "2026-10-26", geographic_scope: "Street-level photo", rights_status: "cleared" };
const model = { model_id: "country-net", version: "1.0.0", runtime: "onnx", is_placeholder: false, description: "Real model.", required_for_learning: false };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const publicRound = (position: number, startedAt: string, limit: number | null = null) => ({
  race_id: "r-1", position, rounds_total: 2, started_at: startedAt, time_limit_seconds: limit,
  round: { round_id: `photo-${position}`, asset_id: `${position}.jpg`, asset_kind: "photo", asset_attribution: attribution, asset_description: `Photo ${position}` },
});
const result = (position: number, submission: object, isCorrect: boolean, extra: object = {}) => ({
  race_id: "r-1", position, finished: position === 2, timed_out: false, model_unavailable: false,
  learner_points: isCorrect ? 1 : 0, model_points: 1, score: { learner: 1, model: position },
  reveal: { round_id: `photo-${position}`, attempt_id: `a-${position}`, is_correct: isCorrect, submission: { skipped: false, uncertain: false, ...submission }, answer: { country_code: "SK", coordinate: null, answer_origin: "source-truth", explanation: "Bratislava, Slovakia.", citations: [attribution] }, study_progress: null },
  model_prediction: { attempt_id: `a-${position}`, round_id: `photo-${position}`, model, abstained: false, origin: "model_prediction", candidates: [{ country_code: "SK", confidence: 0.6 }, { country_code: "CZ", confidence: 0.2 }] },
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("RaceMode", () => {
  it("explains why it cannot race and keeps Start disabled", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ available: false, reason: "Race mode needs a real model; the placeholder model cannot race." })));
    render(<RaceMode />);
    expect(await screen.findByText(/placeholder model cannot race/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start race" })).toBeDisabled();
  });

  it("races two rounds, reveals both guesses only after answering, and shows the summary", async () => {
    const requests: { method: string; url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      requests.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url.endsWith("/races/availability")) return json({ available: true, reason: null });
      if (url.endsWith("/races") && method === "POST") return json({ race_id: "r-1", model, rounds_total: 2, time_limit_seconds: 60 }, 201);
      if (url.endsWith("/rounds/1")) return json(publicRound(1, new Date().toISOString(), 60));
      if (url.endsWith("/rounds/2")) return json(publicRound(2, new Date().toISOString(), 60));
      if (url.endsWith("/rounds/1/answers")) return json(result(1, { country_code: "SK" }, true));
      if (url.endsWith("/rounds/2/answers")) return json(result(2, { skipped: true }, false));
      if (url.endsWith("/races/r-1")) return json({ race_id: "r-1", model, time_limit_seconds: 60, created_at: "2026-11-02T12:00:00Z", finished_at: "2026-11-02T12:02:00Z", score: { learner: 1, model: 2 }, model_missed_rounds: 0, rounds: [
        { position: 1, round_id: "photo-1", asset_id: "1.jpg", answered: true, answer_country_code: "SK", learner_country_code: "SK", model_country_code: "SK", learner_points: 1, model_points: 1 },
        { position: 2, round_id: "photo-2", asset_id: "2.jpg", answered: true, answer_country_code: "SK", learner_country_code: null, model_country_code: "SK", learner_points: 0, model_points: 1 },
      ] });
      return json({ detail: "Unexpected request" }, 500);
    }));
    render(<RaceMode />);

    const start = await screen.findByRole("button", { name: "Start race" });
    await waitFor(() => expect(start).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Time limit per round"), { target: { value: "60" } });
    fireEvent.click(start);

    expect(await screen.findByRole("img", { name: "Photo 1" })).toHaveAttribute("src", "/api/v1/assets/1.jpg");
    expect(screen.getByRole("timer")).toHaveTextContent(/^[01]:\d\d$/);
    expect(document.body.textContent).not.toMatch(/Slovakia|Answer:/);
    const lockIn = screen.getByRole("button", { name: "Lock in guess" });
    expect(lockIn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Country guess/), { target: { value: "slovakia" } });
    fireEvent.click(lockIn);

    const reveal = await screen.findByLabelText("Race round result");
    expect(reveal).toHaveTextContent("Answer: Slovakia (SK)");
    expect(reveal).toHaveTextContent("Slovakia (SK) · 60%");
    expect(screen.getByRole("status")).toHaveTextContent("You 1 : 1 Model");

    fireEvent.click(screen.getByRole("button", { name: "Next round" }));
    fireEvent.click(await screen.findByRole("button", { name: "Skip" }));
    expect(await screen.findByText("You skipped.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "See results" }));

    const summary = await screen.findByLabelText("Race summary");
    expect(summary).toHaveTextContent("The model won. You 1 : 2 Model");
    expect(summary).toHaveTextContent("skipped (+0)");
    expect(requests.find((r) => r.method === "POST" && r.url.endsWith("/races"))?.body).toEqual({ time_limit_seconds: 60, player: "you" });
    expect(requests.filter((r) => r.url.endsWith("/answers")).map((r) => r.body)).toEqual([{ country_code: "SK" }, { skipped: true }]);
    fireEvent.click(screen.getByRole("button", { name: "Race again" }));
    expect(screen.getByRole("button", { name: "Start race" })).toBeInTheDocument();
  });

  it("skips automatically, once, when the round's time runs out", async () => {
    const answers: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/races/availability")) return json({ available: true });
      if (url.endsWith("/races")) return json({ race_id: "r-1", model, rounds_total: 2, time_limit_seconds: 10 }, 201);
      if (url.endsWith("/rounds/1")) return json(publicRound(1, new Date(Date.now() - 11_000).toISOString(), 10));
      if (url.endsWith("/answers")) {
        answers.push(JSON.parse(String(init?.body)));
        return json(result(1, { skipped: true }, false, { timed_out: true }));
      }
      return json({ detail: "Unexpected request" }, 500);
    }));
    render(<RaceMode />);
    const start = await screen.findByRole("button", { name: "Start race" });
    await waitFor(() => expect(start).toBeEnabled());
    fireEvent.click(start);
    expect(await screen.findByText(/Time ran out/)).toBeInTheDocument();
    expect(answers).toEqual([{ skipped: true }]);
  });

  it("runs a projector race for the class with Class labels and a class verdict", async () => {
    const starts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/races/availability")) return json({ available: true });
      if (url.endsWith("/races") && method === "POST") {
        starts.push(JSON.parse(String(init?.body)));
        return json({ race_id: "r-1", model, rounds_total: 2, time_limit_seconds: null, player: "class" }, 201);
      }
      if (url.endsWith("/rounds/2")) return json(publicRound(2, new Date().toISOString()));
      if (url.endsWith("/rounds/2/answers")) return json(result(2, { skipped: true }, false, { score: { learner: 3, model: 2 } }));
      if (url.endsWith("/races/r-1")) return json({ race_id: "r-1", model, player: "class", time_limit_seconds: null, created_at: "2026-11-02T12:00:00Z", finished_at: "2026-11-02T12:02:00Z", score: { learner: 3, model: 2 }, model_missed_rounds: 0, rounds: [] });
      // The class race opens on its final round so one answer finishes it.
      if (url.endsWith("/rounds/1")) return json(publicRound(2, new Date().toISOString()));
      return json({ detail: "Unexpected request" }, 500);
    }));
    render(<RaceMode />);
    const start = await screen.findByRole("button", { name: "Start race" });
    await waitFor(() => expect(start).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Who is racing"), { target: { value: "class" } });
    expect(screen.getByText(/not added to your study review/)).toBeInTheDocument();
    fireEvent.click(start);

    expect(await screen.findByRole("heading", { name: "Class vs Model" })).toBeInTheDocument();
    expect(screen.getByLabelText(/The class's guess/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText("The class skipped.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Class 3 : 2 Model");
    fireEvent.click(screen.getByRole("button", { name: "See results" }));
    const summary = await screen.findByLabelText("Race summary");
    expect(summary).toHaveTextContent("The class won! Class 3 : 2 Model");
    expect(summary).toHaveTextContent("Class answers were not added to your study review.");
    expect(starts).toEqual([{ time_limit_seconds: null, player: "class" }]);
  });
});
