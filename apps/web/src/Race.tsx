import { useEffect, useRef, useState } from "react";

import {
  GeoCompanionApiClient,
  type RaceAvailability,
  type RaceRoundPublic,
  type RaceRoundResult,
  type RaceStarted,
  type RaceSummary,
} from "./api/generated";
import { AttributionDetails } from "./AttributionDetails";
import { COUNTRY_OPTIONS, country, parseCountryGuess } from "./countries";

// Race mode (docs/race-mode-plan.md): the learner and the model guess the same photos. The
// server keeps the answer and the model's guess until the learner has answered each round.
const client = new GeoCompanionApiClient();

// Per-round limits like GeoGuessr's game settings; the server accepts 10 to 600 seconds.
const TIME_LIMITS: { label: string; seconds: number | null }[] = [
  { label: "No time limit", seconds: null },
  { label: "10 seconds", seconds: 10 },
  { label: "30 seconds", seconds: 30 },
  { label: "1 minute", seconds: 60 },
  { label: "2 minutes", seconds: 120 },
  { label: "3 minutes", seconds: 180 },
  { label: "5 minutes", seconds: 300 },
];

function message(error: unknown) {
  return error instanceof Error ? error.message : "The local learning service is unavailable.";
}

function photoUrl(assetId: string) {
  return `/api/v1/assets/${encodeURIComponent(assetId)}`;
}

function scoreLine(learner: number, model: number) {
  return `You ${learner} : ${model} Model`;
}

function secondsLeft(round: RaceRoundPublic, now: number) {
  if (round.time_limit_seconds == null) return null;
  const deadline = Date.parse(round.started_at) + round.time_limit_seconds * 1000;
  return Math.max(0, Math.ceil((deadline - now) / 1000));
}

function clock(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function Mark({ right }: { right: boolean }) {
  return <strong>{right ? "right" : "wrong"}</strong>;
}

function RoundReveal({ result }: { result: RaceRoundResult }) {
  const { reveal, model_prediction: prediction } = result;
  const guess = reveal.submission.country_code;
  return (
    <div className="result" aria-label="Race round result">
      <p>Answer: <strong>{country(reveal.answer.country_code)}</strong></p>
      <div className="race-sides">
        <div className="race-side">
          <p className="model-name">You</p>
          {result.timed_out ? <p>Time ran out, so this round counts as a skip.</p>
            : reveal.submission.skipped ? <p>You skipped.</p>
            : <p>{guess ? country(guess) : "No guess"}: <Mark right={reveal.is_correct} /></p>}
          <p>+{result.learner_points}</p>
        </div>
        <div className="race-side">
          <p className="model-name">Model</p>
          {result.model_unavailable || !prediction ? <p>The model was unavailable this round.</p>
            : prediction.abstained ? <p>The model abstained: it was not confident enough to guess.</p>
            : <>
              <p>{country(prediction.candidates[0].country_code)}: <Mark right={result.model_points === 1} /></p>
              <ol className="origin">
                {prediction.candidates.map((candidate) => <li key={candidate.country_code}>{country(candidate.country_code)} · {Math.round(candidate.confidence * 100)}%</li>)}
              </ol>
            </>}
          <p>+{result.model_points}</p>
        </div>
      </div>
      <p className="outcome" role="status">{scoreLine(result.score.learner, result.score.model)}</p>
      <p>{reveal.answer.explanation}</p>
      {reveal.answer.citations.map((citation, index) => <AttributionDetails key={index} attribution={citation} label="Answer citation" />)}
    </div>
  );
}

function Summary({ summary, onAgain }: { summary: RaceSummary; onAgain: () => void }) {
  const { learner, model } = summary.score;
  const verdict = learner > model ? "You won!" : learner < model ? "The model won." : "It's a draw.";
  return (
    <div aria-label="Race summary">
      <p className="outcome">{verdict} {scoreLine(learner, model)}</p>
      <table className="accuracy">
        <caption>Every round of this race</caption>
        <thead><tr><th scope="col">Round</th><th scope="col">Answer</th><th scope="col">You</th><th scope="col">Model</th></tr></thead>
        <tbody>
          {summary.rounds.map((row) => <tr key={row.position}>
            <th scope="row">{row.position}</th>
            <td>{row.answer_country_code ? country(row.answer_country_code) : "—"}</td>
            <td>{row.timed_out ? "time ran out" : row.learner_country_code ? country(row.learner_country_code) : "skipped"} (+{row.learner_points ?? 0})</td>
            <td>{row.model_unavailable ? "unavailable" : row.model_country_code ? country(row.model_country_code) : "abstained"} (+{row.model_points ?? 0})</td>
          </tr>)}
        </tbody>
      </table>
      {summary.model_missed_rounds > 0 && <p className="origin">The model was unavailable for {summary.model_missed_rounds} of these rounds.</p>}
      <p className="origin">Raced against {summary.model.model_id} {summary.model.version}. Your answers were also saved as practice for study review.</p>
      <div className="actions"><button type="button" onClick={onAgain}>Race again</button></div>
    </div>
  );
}

export function RaceMode() {
  const [availability, setAvailability] = useState<RaceAvailability | null>(null);
  const [limit, setLimit] = useState<number | null>(null);
  const [race, setRace] = useState<RaceStarted | null>(null);
  const [round, setRound] = useState<RaceRoundPublic | null>(null);
  const [result, setResult] = useState<RaceRoundResult | null>(null);
  const [summary, setSummary] = useState<RaceSummary | null>(null);
  const [guess, setGuess] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // One automatic skip per round when the clock reaches zero.
  const autoSkipped = useRef<string | null>(null);

  useEffect(() => {
    client.race_availability_api_v1_races_availability_get().then(setAvailability, (caught: unknown) => setError(message(caught)));
  }, []);

  const run = async (action: () => Promise<void>) => {
    try {
      setPending(true);
      setError(null);
      await action();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setPending(false);
    }
  };

  const openRound = async (raceId: string, position: number) => {
    const next = await client.get_race_round_api_v1_races__race_id__rounds__position__get(raceId, position);
    setRound(next);
    setResult(null);
    setGuess("");
    setNow(Date.now());
  };

  const start = () => run(async () => {
    const started = await client.start_race_api_v1_races_post({ time_limit_seconds: limit });
    setRace(started);
    setSummary(null);
    await openRound(started.race_id, 1);
  });

  const guessCode = parseCountryGuess(guess);

  const answer = (skipped: boolean) => {
    if (!round) return Promise.resolve();
    return run(async () => {
      const body = skipped ? { skipped: true } : { country_code: guessCode ?? undefined };
      setResult(await client.answer_race_round_api_v1_races__race_id__rounds__position__answers_post(round.race_id, round.position, body));
    });
  };

  const next = () => run(async () => {
    if (!round || !result) return;
    if (result.finished) {
      setSummary(await client.get_race_api_v1_races__race_id__get(round.race_id));
      setRound(null);
      setResult(null);
    } else {
      await openRound(round.race_id, round.position + 1);
    }
  });

  const reset = () => {
    setRace(null);
    setRound(null);
    setResult(null);
    setSummary(null);
  };

  const left = round && !result ? secondsLeft(round, now) : null;

  useEffect(() => {
    if (!round || result || round.time_limit_seconds == null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [round, result]);

  useEffect(() => {
    if (left !== 0 || !round || result || pending) return;
    const key = `${round.race_id}/${round.position}`;
    if (autoSkipped.current === key) return;
    autoSkipped.current = key;
    void answer(true);
    // answer() reads the current round; this effect only needs to run when the clock hits zero.
  }, [left, round, result, pending]);

  return (
    <section aria-labelledby="race-title">
      <h2 id="race-title">Race the model</h2>
      {error && <p role="alert">{error}</p>}
      {!race && !summary && <>
        <p>You and the model guess the same 5 street-level photos. Neither of you sees the other's guess until you answer. Each right country is worth 1 point.</p>
        {!availability && !error && <p>Checking whether the model can race…</p>}
        {availability && !availability.available && <p className="notice">{availability.reason}</p>}
        <label htmlFor="race-limit">Time limit per round</label>
        <select id="race-limit" value={limit ?? ""} onChange={(event) => setLimit(event.target.value === "" ? null : Number(event.target.value))}>
          {TIME_LIMITS.map((option) => <option key={option.label} value={option.seconds ?? ""}>{option.label}</option>)}
        </select>
        <div className="actions">
          <button type="button" disabled={pending || !availability?.available} onClick={() => void start()}>Start race</button>
        </div>
      </>}
      {race && round && <>
        <p className="round-id">Round {round.position} of {round.rounds_total} · racing {race.model.model_id} {race.model.version}</p>
        {left !== null && <p className="race-clock" role="timer" aria-label="Time left">{clock(left)}</p>}
        <img className="fixture photo" src={photoUrl(round.round.asset_id)} alt={round.round.asset_description} />
        <AttributionDetails attribution={round.round.asset_attribution} label="Photo attribution" />
        {!result ? <div className="attempt">
          <p className="origin">The model is ready. Its guess stays hidden until you answer.</p>
          <label htmlFor="race-guess">Country guess (type to search, e.g. France or FR)</label>
          <input id="race-guess" list="race-country-options" value={guess} onChange={(event) => setGuess(event.target.value)} autoComplete="off" />
          <datalist id="race-country-options">
            {COUNTRY_OPTIONS.map((option) => <option key={option.code} value={option.label} />)}
          </datalist>
          <div className="actions">
            <button type="button" disabled={pending || guessCode === null} onClick={() => void answer(false)}>Lock in guess</button>
            <button type="button" disabled={pending} onClick={() => void answer(true)}>Skip</button>
          </div>
        </div> : <>
          <RoundReveal result={result} />
          <div className="actions">
            <button type="button" disabled={pending} onClick={() => void next()}>{result.finished ? "See results" : "Next round"}</button>
          </div>
        </>}
      </>}
      {summary && <Summary summary={summary} onAgain={reset} />}
    </section>
  );
}
