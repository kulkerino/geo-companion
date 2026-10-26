import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AsgiBridge } from "./test/asgiBridge";

// Combined test: the rendered React app's fetch calls are answered by the real FastAPI app and
// LearningService in a separate Python process, persisting to one temporary SQLite database.
const bridges: AsgiBridge[] = [];
const dataDirs: string[] = [];

async function startApi(dataDir: string, env: Record<string, string> = {}) {
  const bridge = await AsgiBridge.start(dataDir, env);
  bridges.push(bridge);
  vi.stubGlobal("fetch", bridge.fetch);
  return bridge;
}

function freshDataDir() {
  const dir = mkdtempSync(join(tmpdir(), "geo-companion-combined-"));
  dataDirs.push(dir);
  return dir;
}

const pageText = () => document.body.textContent ?? "";
const utcDate = (offsetDays: number) => new Date(Date.now() + offsetDays * 86_400_000).toISOString().slice(0, 10);

afterEach(async () => {
  vi.unstubAllGlobals();
  await Promise.all(bridges.splice(0).map((bridge) => bridge.stop()));
  for (const dir of dataDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("App with the real API and SQLite", () => {
  it("runs practice, report, retry, next, review, and reload against persisted local state", async () => {
    const dataDir = freshDataDir();
    const api = await startApi(dataDir);
    const first = render(<App />);

    // Public round: the diagram evidence is shown, but no answer or explanation is in the page.
    const diagram = await screen.findByRole("img", { name: /place-name panel reading BRATISLAVA/ });
    expect(diagram).toHaveAttribute("src", "/starter-assets/place-panel-01.svg");
    const attribution = screen.getByLabelText("Diagram attribution");
    for (const field of ["CC0-1.0", "Geo Companion project contributors", "cleared", "Synthetic classroom scene", "2026-10-14 / 2026-10-14"]) {
      expect(within(attribution).getByText(field, { exact: false })).toBeInTheDocument();
    }
    expect(within(attribution).getByRole("link", { name: "CC0-1.0" })).toHaveAttribute("href", "https://creativecommons.org/publicdomain/zero/1.0/");
    expect(pageText()).not.toMatch(/Slovakia|Authored teaching target|Answer:/);
    expect(screen.queryByRole("button", { name: "Compare with model" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reveal optional clue" }));
    expect(await screen.findByText(/Read both panels/)).toBeInTheDocument();
    expect(pageText()).not.toMatch(/Slovakia|Answer:/);

    // A wrong confident guess is scored by the API and reveals the authored target.
    fireEvent.change(screen.getByLabelText(/Country-code guess/), { target: { value: "cz" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit guess" }));
    expect(await screen.findByText("Not correct: you guessed CZ.")).toBeInTheDocument();
    expect(screen.getByText("SK")).toBeInTheDocument();
    expect(screen.getByText(/Authored teaching target: Slovakia\. Cue: the place-name panel reads BRATISLAVA/)).toBeInTheDocument();
    expect(screen.getByLabelText("Answer citation")).toHaveTextContent("cleared");
    expect(screen.getByText(`Next review of starter-place-01 on ${utcDate(1)} (interval 1 day, ease 2.18).`)).toBeInTheDocument();

    // The placeholder model's opinion is only offered after the answer, clearly labelled.
    fireEvent.click(await screen.findByRole("button", { name: "Compare with model" }));
    const comparison = await screen.findByLabelText("Model comparison");
    expect(comparison).toHaveTextContent("dummy-placeholder 0.1.0 (placeholder, not real inference)");
    expect(within(comparison).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["CH · 27%", "PT · 19%", "BG · 13%"]);
    expect(screen.getByText("SK")).toBeInTheDocument();

    // The report is stored against this exact attempt in SQLite and leaves the answer untouched.
    fireEvent.click(screen.getByRole("button", { name: "Report issue" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Report saved locally for this attempt");
    const database = new DatabaseSync(join(dataDir, "runtime.sqlite3"));
    expect(database.prepare("SELECT round_id, is_correct, reported_issue FROM learner_practice_attempts").all())
      .toEqual([{ round_id: "starter-place-01", is_correct: 0, reported_issue: 1 }]);
    expect(database.prepare("SELECT round_id, reported_issue FROM learner_feedback").all())
      .toEqual([{ round_id: "starter-place-01", reported_issue: 1 }]);
    expect(database.prepare("SELECT round_id, model_id FROM learner_model_predictions").all())
      .toEqual([{ round_id: "starter-place-01", model_id: "dummy-placeholder" }]);

    // Retry keeps the same round and clears the attempt; an uncertain correct answer is scored.
    fireEvent.click(screen.getByRole("button", { name: "Retry same round" }));
    expect(screen.getByRole("img", { name: /BRATISLAVA/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Country-code guess/)).toHaveValue("");
    expect(pageText()).not.toMatch(/Slovakia|Answer:|Read both panels/);
    fireEvent.change(screen.getByLabelText(/Country-code guess/), { target: { value: "SK" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit uncertain guess" }));
    expect(await screen.findByText("Correct (marked uncertain).")).toBeInTheDocument();
    expect(screen.getByText(`Next review of starter-place-01 on ${utcDate(1)} (interval 1 day, ease 2.04).`)).toBeInTheDocument();

    // Next round advances to the following round (the retry did not skip one) and can be skipped.
    fireEvent.click(screen.getByRole("button", { name: "Next round" }));
    expect(await screen.findByRole("img", { name: /place-name panel reading BRNO/ })).toBeInTheDocument();
    expect(pageText()).not.toMatch(/Czechia|Answer:/);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText("Skipped.")).toBeInTheDocument();
    expect(screen.getByText(/Authored teaching target: Czechia/)).toBeInTheDocument();

    // The study queue is ordered by due date; both rounds are due tomorrow, so the ID breaks the tie.
    fireEvent.click(screen.getByRole("button", { name: "Study review" }));
    expect(await screen.findByText(`Next review of starter-place-01 on ${utcDate(1)} (interval 1 day, ease 2.04).`)).toBeInTheDocument();
    expect(database.prepare("SELECT COUNT(*) AS attempts FROM learner_practice_attempts").get()).toEqual({ attempts: 3 });
    database.close();

    // Reload: a new API process and a fresh React tree read the same SQLite database.
    first.unmount();
    await api.stop();
    await startApi(dataDir);
    render(<App />);
    expect(await screen.findByRole("img", { name: /place-name panel reading GRAZ/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Study review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Practice this round" }));
    expect(await screen.findByRole("img", { name: /place-name panel reading BRATISLAVA/ })).toBeInTheDocument();
    expect(pageText()).not.toMatch(/Slovakia|Answer:/);
  }, 60_000);

  it("guesses an uploaded photo through the real API without storing it", async () => {
    const dataDir = freshDataDir();
    await startApi(dataDir);
    Object.assign(URL, { createObjectURL: () => "blob:preview", revokeObjectURL: () => {} });
    render(<App />);

    await screen.findByRole("img", { name: /BRATISLAVA/ });
    fireEvent.click(screen.getByRole("button", { name: "Your photo" }));
    const photo = new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3])], "trip.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText(/Photo \(JPEG/), { target: { files: [photo] } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask the model" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Ask the model" }));

    const guess = await screen.findByLabelText("Model guess for your photo");
    expect(guess).toHaveTextContent("dummy-placeholder 0.1.0 (placeholder, not real inference)");
    expect(guess).toHaveTextContent(/abstained|%/);
    expect(guess).toHaveTextContent("not graded and is not saved");
    const database = new DatabaseSync(join(dataDir, "runtime.sqlite3"));
    expect(database.prepare("SELECT COUNT(*) AS rows FROM learner_model_predictions").get()).toEqual({ rows: 0 });
    database.close();
  }, 60_000);

  it("runs practice without a model when the model is switched off", async () => {
    await startApi(freshDataDir(), { GEO_COMPANION_MODEL: "none" });
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Skip" }));
    expect(await screen.findByText("Skipped.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Compare with model" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  }, 60_000);

  it("shows the real API failure instead of fabricating a round", async () => {
    // A file where the data directory should be makes the real service fail to open SQLite.
    const blocked = join(freshDataDir(), "not-a-directory");
    writeFileSync(blocked, "");
    await startApi(blocked);
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Geo Companion API request failed: 500");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  }, 60_000);
});
