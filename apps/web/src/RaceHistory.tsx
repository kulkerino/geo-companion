import { useEffect, useState } from "react";

import {
  GeoCompanionApiClient,
  type ModelBenchmarks,
  type ModelInfo,
  type RaceHistory as RaceHistoryData,
  type RaceTally,
} from "./api/generated";

// Race mode step 5 (docs/race-mode-plan.md): you against the model over all finished races,
// and each model version's score on the same fixed photos. Only totals come from the server.
const client = new GeoCompanionApiClient();

function message(error: unknown) {
  return error instanceof Error ? error.message : "The local learning service is unavailable.";
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function modelName(model: ModelInfo) {
  return `${model.model_id} ${model.version}`;
}

function record(tally: RaceTally) {
  const races = tally.races === 1 ? "1 race" : `${tally.races} races`;
  return `You won ${tally.learner_wins}, the model won ${tally.model_wins}, ${tally.draws} drawn, over ${races} (points: you ${tally.learner_points}, model ${tally.model_points}).`;
}

function limitName(seconds: number | null | undefined) {
  if (seconds == null) return "no limit";
  return seconds < 60 ? `${seconds} s` : `${seconds / 60} min`;
}

export function RaceHistory() {
  const [history, setHistory] = useState<RaceHistoryData | null>(null);
  const [benchmarks, setBenchmarks] = useState<ModelBenchmarks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const load = () => Promise.all([
    client.get_race_history_api_v1_races_history_get().then(setHistory),
    client.model_benchmarks_api_v1_models_benchmarks_get().then(setBenchmarks),
  ]);

  useEffect(() => {
    load().catch((caught: unknown) => setError(message(caught)));
  }, []);

  const runBenchmark = async () => {
    try {
      setPending(true);
      setError(null);
      await client.run_model_benchmark_api_v1_models_benchmarks_post();
      await load();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setPending(false);
    }
  };

  const current = benchmarks?.runs.filter((run) => run.photo_set_id === benchmarks.photo_set_id) ?? [];
  const otherSets = (benchmarks?.runs.length ?? 0) - current.length;

  return (
    <section aria-labelledby="history-title">
      <h2 id="history-title">Race history</h2>
      {error && <p role="alert">{error}</p>}
      {!history && !error && <p>Loading your races…</p>}
      {history && (history.overall.races === 0 ? <p>No finished races yet. Finish a race in "Race the model" to start your record.</p> : <>
        <p className="outcome">{record(history.overall)}</p>
        <table className="accuracy">
          <caption>You against each model version</caption>
          <thead><tr><th scope="col">Model</th><th scope="col">Races</th><th scope="col">You won</th><th scope="col">Model won</th><th scope="col">Drawn</th><th scope="col">Your points</th><th scope="col">Model points</th></tr></thead>
          <tbody>
            {history.by_model.map(({ model, tally }) => <tr key={modelName(model)}>
              <th scope="row">{modelName(model)}</th>
              <td>{tally.races}</td><td>{tally.learner_wins}</td><td>{tally.model_wins}</td><td>{tally.draws}</td>
              <td>{tally.learner_points} of {tally.rounds}</td><td>{tally.model_points} of {tally.rounds}</td>
            </tr>)}
          </tbody>
        </table>
        <table className="accuracy">
          <caption>Finished races, newest first</caption>
          <thead><tr><th scope="col">Finished</th><th scope="col">Model</th><th scope="col">Time limit</th><th scope="col">Score</th></tr></thead>
          <tbody>
            {history.races.map((race) => <tr key={race.race_id}>
              <th scope="row">{new Date(race.finished_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</th>
              <td>{modelName(race.model)}</td>
              <td>{limitName(race.time_limit_seconds)}</td>
              <td>You {race.score.learner} : {race.score.model} Model</td>
            </tr>)}
          </tbody>
        </table>
      </>)}

      <h3>Model progress</h3>
      {benchmarks && <>
        <p>
          Each model version guesses the same {benchmarks.photo_rounds} race photos once, seeing only the photo, like in a race.
          The same photos for every version make the scores comparable.
        </p>
        {current.length > 0 ? <table className="accuracy">
          <caption>Right country on the fixed race photos, oldest model first</caption>
          <thead><tr><th scope="col">Model</th><th scope="col">Right</th><th scope="col">Abstained</th><th scope="col">Failed</th></tr></thead>
          <tbody>
            {current.map((run) => <tr key={modelName(run.model)}>
              <th scope="row">{modelName(run.model)}</th>
              <td><span className="bar" style={{ width: `${run.accuracy * 12}rem` }} aria-hidden="true" /> {percent(run.accuracy)} ({run.correct} of {run.rounds})</td>
              <td>{run.abstained}</td>
              <td>{run.failed}</td>
            </tr>)}
          </tbody>
        </table> : <p>No model version has been scored on these photos yet.</p>}
        {otherSets > 0 && <p className="origin">{otherSets} earlier {otherSets === 1 ? "run used" : "runs used"} a different set of photos, so {otherSets === 1 ? "it is" : "they are"} not shown here.</p>}
        {!benchmarks.can_run && <p className="notice">{benchmarks.reason}</p>}
        <div className="actions">
          <button type="button" disabled={pending || !benchmarks.can_run} onClick={() => void runBenchmark()}>Score the current model on these photos</button>
        </div>
        {pending && <p role="status">The model is guessing {benchmarks.photo_rounds} photos…</p>}
      </>}
    </section>
  );
}
