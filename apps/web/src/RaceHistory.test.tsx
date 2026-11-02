import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RaceHistory } from "./RaceHistory";

const model = (version: string) => ({ model_id: "country-net", version, runtime: "onnx", is_placeholder: false, description: "Real model.", required_for_learning: false });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const tally = (races: number, learner: number, modelPoints: number, wins: [number, number, number]) => ({
  races, rounds: races * 5, learner_points: learner, model_points: modelPoints, learner_wins: wins[0], model_wins: wins[1], draws: wins[2],
});
const run = (version: string, correct: number, setId = "photos-200-abc") => ({
  model: model(version), photo_set_id: setId, rounds: 200, correct, abstained: 10, failed: 0, accuracy: correct / 200, created_at: "2026-11-02T12:00:00Z",
});
const emptyHistory = { races: [], overall: tally(0, 0, 0, [0, 0, 0]), by_model: [] };

afterEach(() => vi.unstubAllGlobals());

describe("RaceHistory", () => {
  it("shows the record per model version and the progress of each version on the same photos", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/races/history")) return json({
        races: [{ race_id: "r-2", model: model("1.1.0"), time_limit_seconds: 30, created_at: "2026-11-02T12:00:00Z", finished_at: "2026-11-02T12:05:00Z", score: { learner: 2, model: 4 }, rounds_total: 5 }],
        overall: tally(3, 9, 10, [1, 1, 1]),
        by_model: [{ model: model("1.0.0"), tally: tally(2, 7, 6, [1, 0, 1]) }, { model: model("1.1.0"), tally: tally(1, 2, 4, [0, 1, 0]) }],
      });
      if (url.endsWith("/models/benchmarks")) return json({
        photo_set_id: "photos-200-abc", photo_rounds: 200, can_run: true, reason: null,
        runs: [run("1.0.0", 80), run("1.1.0", 110), run("0.9.0", 50, "photos-150-old")],
      });
      return json({ detail: "Unexpected request" }, 500);
    }));
    render(<RaceHistory />);

    expect(await screen.findByText(/You won 1, the model won 1, 1 drawn, over 3 races/)).toBeInTheDocument();
    const versions = within(screen.getByRole("table", { name: "You against each model version" })).getAllByRole("row");
    expect(versions[1]).toHaveTextContent("country-net 1.0.0");
    expect(versions[2]).toHaveTextContent("country-net 1.1.0");
    expect(screen.getByRole("table", { name: /Finished races/ })).toHaveTextContent("You 2 : 4 Model");

    const progress = within(screen.getByRole("table", { name: /fixed race photos/ })).getAllByRole("row");
    expect(progress).toHaveLength(3);
    expect(progress[1]).toHaveTextContent("40% (80 of 200)");
    expect(progress[2]).toHaveTextContent("55% (110 of 200)");
    expect(screen.getByText(/1 earlier run used a different set of photos/)).toBeInTheDocument();
  });

  it("explains an empty history and why the placeholder cannot be scored", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/races/history")) return json(emptyHistory);
      return json({ photo_set_id: null, photo_rounds: 0, runs: [], can_run: false, reason: "Race mode needs a real model; the placeholder model cannot race." });
    }));
    render(<RaceHistory />);
    expect(await screen.findByText(/No finished races yet/)).toBeInTheDocument();
    expect(screen.getByText(/placeholder model cannot race/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Score the current model/ })).toBeDisabled();
  });

  it("scores the current model, then reloads the progress table", async () => {
    let runs: ReturnType<typeof run>[] = [];
    const posts: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/races/history")) return json(emptyHistory);
      if (url.endsWith("/models/benchmarks") && init?.method === "POST") {
        posts.push(url);
        runs = [run("1.0.0", 100)];
        return json(runs[0]);
      }
      return json({ photo_set_id: "photos-200-abc", photo_rounds: 200, runs, can_run: true, reason: null });
    }));
    render(<RaceHistory />);
    fireEvent.click(await screen.findByRole("button", { name: /Score the current model/ }));
    await waitFor(() => expect(screen.getByText("50% (100 of 200)")).toBeInTheDocument());
    expect(posts).toHaveLength(1);
  });
});
