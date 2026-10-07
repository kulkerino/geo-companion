import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const attribution = { source_title: "Original fixture", source_url: "https://creativecommons.org/publicdomain/zero/1.0/", creator: "Geo Companion contributors", license_name: "CC0-1.0", license_url: "https://creativecommons.org/publicdomain/zero/1.0/", attribution_text: "Original educational diagram, not Street View or OSV imagery.", accessed_on: "2026-10-07", reviewed_on: "2026-10-07", geographic_scope: "Synthetic classroom scene", rights_status: "cleared" };
const response = (body: unknown, status = 200) => new Response(body === undefined ? undefined : JSON.stringify(body), { status, headers: body === undefined ? undefined : { "content-type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("uses real generated-client requests without leaking a practice answer before submission", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/lessons")) return response({ lessons: [{ lesson_id: "lesson-1", title: "Signs" }] });
      if (url.endsWith("/api/v1/lessons/lesson-1")) return response({ lesson_id: "lesson-1", title: "Signs", body: "Compare independent clues.", citations: [attribution], quiz_items: [{ quiz_id: "quiz-1", prompt: "Which is cautious?", choices: ["Compare clues", "Guess once"] }] });
      if (url.endsWith("/quizzes/quiz-1/answers")) { expect(JSON.parse(String(init?.body))).toEqual({ selected_choice: "Compare clues" }); return response({ lesson_id: "lesson-1", quiz_id: "quiz-1", selected_choice: "Compare clues", is_correct: true, explanation: "Compare multiple clues.", citations: [attribution] }); }
      if (url.endsWith("/api/v1/study/grades")) return response({ lesson_id: "lesson-1", repetitions: 1, interval_days: 1, ease_factor: 2.5, last_reviewed_on: "2026-10-07" });
      if (url.endsWith("/api/v1/practice/rounds/next")) return response({ round_id: "round-1", asset_id: "diagram-01.svg", asset_attribution: attribution });
      if (url.endsWith("/practice/rounds/round-1/clue")) return response({ round_id: "round-1", clue: "A cautious clue." });
      if (url.endsWith("/practice/rounds/round-1/answers")) { expect(JSON.parse(String(init?.body))).toEqual({ skipped: true, uncertain: false }); return response({ round_id: "round-1", attempt_id: "attempt-1", is_correct: false, submission: { skipped: true, uncertain: false }, answer: { country_code: "ZZ", coordinate: null, answer_origin: "authored", explanation: "Teaching target: Zedland.", citations: [attribution] } }); }
      if (url.endsWith("/api/v1/feedback")) { expect(JSON.parse(String(init?.body))).toMatchObject({ attempt_id: "attempt-1", reported_issue: true }); return response(undefined, 204); }
      return response({ detail: "Unexpected request" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Signs" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Compare clues" }));
    expect(await screen.findByText("Compare multiple clues.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    expect(await screen.findByText(/review scheduled in 1 day/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Practice" }));
    expect(await screen.findByText(/Original educational diagram/i)).toBeInTheDocument();
    expect(screen.queryByText(/Teaching target: Zedland/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reveal optional clue" }));
    expect(await screen.findByText("A cautious clue.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText(/Teaching target: Zedland/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Report issue" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/feedback"), expect.objectContaining({ method: "POST" })));
  });

  it("shows an API error instead of fabricating a result", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ detail: "offline data unavailable" }, 503)));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("offline data unavailable");
  });
});
