import { useEffect, useState } from "react";

import {
  GeoCompanionApiClient,
  type Attribution,
  type ModelInfo,
  type ModelPredictionResult,
  type PracticeAnswerResult,
  type PracticeRoundPublic,
  type StudyProgress,
} from "./api/generated";
import "./app.css";

const client = new GeoCompanionApiClient();
type View = "practice" | "study";

function message(error: unknown) {
  return error instanceof Error ? error.message : "The local learning service is unavailable.";
}

function days(count: number) {
  return `${count} ${count === 1 ? "day" : "days"}`;
}

function AttributionDetails({ attribution, label }: { attribution: Attribution; label: string }) {
  return (
    <dl className="source" aria-label={label}>
      <dt>Source</dt>
      <dd>
        <a href={attribution.source_url} target="_blank" rel="noreferrer noopener">{attribution.source_title}</a>
      </dd>
      <dt>Attribution</dt>
      <dd>{attribution.attribution_text}</dd>
      <dt>Creator</dt>
      <dd>{attribution.creator}</dd>
      <dt>License</dt>
      <dd>
        <a href={attribution.license_url} target="_blank" rel="noreferrer noopener">{attribution.license_name}</a>
      </dd>
      <dt>Rights status</dt>
      <dd>{attribution.rights_status}</dd>
      <dt>Geographic scope</dt>
      <dd>{attribution.geographic_scope}</dd>
      <dt>Accessed / reviewed</dt>
      <dd>{attribution.accessed_on} / {attribution.reviewed_on}</dd>
    </dl>
  );
}

function Schedule({ progress }: { progress: StudyProgress }) {
  return (
    <p>
      Next review of {progress.round_id} on {progress.next_review_on} (interval {days(progress.interval_days)}, ease {progress.ease_factor}).
    </p>
  );
}

function ModelComparison({ prediction }: { prediction: ModelPredictionResult }) {
  const { model } = prediction;
  return (
    <div className="model" aria-label="Model comparison">
      <p className="model-name">
        Model opinion: {model.model_id} {model.version}{model.is_placeholder ? " (placeholder, not real inference)" : ""}
      </p>
      <p className="origin">{model.description}</p>
      {prediction.abstained ? <p>The model abstained: it was not confident enough to guess.</p> : (
        <ol>
          {prediction.candidates.map((candidate) => <li key={candidate.country_code}>{candidate.country_code} · {Math.round(candidate.confidence * 100)}%</li>)}
        </ol>
      )}
      <p className="origin">Model output is stored separately and never changes the authored answer.</p>
    </div>
  );
}

function outcome(reveal: PracticeAnswerResult) {
  if (reveal.submission.skipped) return "Skipped.";
  const confidence = reveal.submission.uncertain ? " (marked uncertain)" : "";
  return reveal.is_correct
    ? `Correct${confidence}.`
    : `Not correct${confidence}: you guessed ${reveal.submission.country_code ?? "nothing"}.`;
}

function App() {
  const [view, setView] = useState<View>("practice");
  const [round, setRound] = useState<PracticeRoundPublic | null>(null);
  const [clue, setClue] = useState<string | null>(null);
  const [reveal, setReveal] = useState<PracticeAnswerResult | null>(null);
  const [guess, setGuess] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [review, setReview] = useState<StudyProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [prediction, setPrediction] = useState<ModelPredictionResult | null>(null);

  const startRound = (next: PracticeRoundPublic) => {
    setRound(next);
    setClue(null);
    setReveal(null);
    setGuess("");
    setNotice(null);
    setPrediction(null);
  };

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

  const loadNextRound = () => run(async () => startRound(await client.next_practice_round_api_v1_practice_rounds_next_get()));

  useEffect(() => {
    void loadNextRound();
    // The model is optional: if its status cannot be read, practice simply runs without it.
    void client.model_status_api_v1_models_get().then((status) => setModel(status.active ?? null), () => setModel(null));
    // Only the first render loads a round; later loads are explicit learner actions.
  }, []);

  const openPractice = () => setView("practice");

  const openStudy = () => {
    setView("study");
    void run(async () => setReview((await client.next_study_review_api_v1_study_review_next_get()).progress ?? null));
  };

  const practiceReview = (roundId: string) => run(async () => {
    startRound(await client.get_practice_round_api_v1_practice_rounds__round_id__get(roundId));
    setView("practice");
  });

  const revealClue = (roundId: string) => run(async () => setClue((await client.get_practice_clue_api_v1_practice_rounds__round_id__clue_get(roundId)).clue));

  const submitPractice = (roundId: string, skipped: boolean, uncertain: boolean) => run(async () => {
    const body = skipped ? { skipped: true, uncertain } : { country_code: guess.trim().toUpperCase(), uncertain };
    setReveal(await client.submit_practice_answer_api_v1_practice_rounds__round_id__answers_post(roundId, body));
  });

  const sendFeedback = (result: PracticeAnswerResult, reportedIssue: boolean) => run(async () => {
    await client.submit_feedback_api_v1_feedback_post({
      attempt_id: result.attempt_id,
      round_id: result.round_id,
      rating: reportedIssue ? 1 : 4,
      note: reportedIssue ? "Learner reported an issue with this round." : "Useful round.",
      reported_issue: reportedIssue,
    });
    setNotice(reportedIssue ? "Report saved locally for this attempt; it does not replace the authored answer." : "Feedback saved locally.");
  });

  const compareWithModel = (result: PracticeAnswerResult) => run(async () => {
    setPrediction(await client.get_model_prediction_api_v1_practice_attempts__attempt_id__model_prediction_get(result.attempt_id));
  });

  const retrySameRound = () => {
    if (round) startRound(round);
  };

  const validGuess = /^[A-Za-z]{2}$/.test(guess.trim());

  return (
    <main className="shell">
      <p className="eyebrow">Local learning companion · offline starter pack</p>
      <h1>Geo Companion</h1>
      <nav aria-label="Learning modes" className="tabs">
        <button type="button" aria-pressed={view === "practice"} onClick={openPractice}>Open Practice</button>
        <button type="button" aria-pressed={view === "study"} onClick={openStudy}>Study review</button>
      </nav>
      {error && <p role="alert">{error}</p>}
      {view === "practice" && <section aria-labelledby="practice-title">
        <h2 id="practice-title">Open Practice</h2>
        {!round && !error && <p>Loading a practice round…</p>}
        {round && <>
          <p className="round-id">Round {round.round_id}</p>
          <img className="fixture" src={`/starter-assets/${encodeURIComponent(round.asset_id)}`} alt={round.asset_description} />
          <AttributionDetails attribution={round.asset_attribution} label="Diagram attribution" />
          {!reveal ? <div className="attempt">
            <button type="button" onClick={() => void revealClue(round.round_id)}>Reveal optional clue</button>
            {clue && <p className="clue">{clue}</p>}
            <label htmlFor="guess">Country-code guess (two letters, e.g. FR)</label>
            <input id="guess" value={guess} onChange={(event) => setGuess(event.target.value)} maxLength={2} autoComplete="off" />
            <div className="actions">
              <button type="button" disabled={pending || !validGuess} onClick={() => void submitPractice(round.round_id, false, false)}>Submit guess</button>
              <button type="button" disabled={pending || !validGuess} onClick={() => void submitPractice(round.round_id, false, true)}>Submit uncertain guess</button>
              <button type="button" disabled={pending} onClick={() => void submitPractice(round.round_id, true, false)}>Skip</button>
            </div>
          </div> : <div className="result">
            <p className="outcome">{outcome(reveal)}</p>
            <p>Answer: <strong>{reveal.answer.country_code}</strong></p>
            <p>{reveal.answer.explanation}</p>
            <p className="origin">Answer origin: {reveal.answer.answer_origin}. Your feedback and reports are stored separately and never change it.</p>
            {reveal.answer.citations.map((citation, index) => <AttributionDetails key={index} attribution={citation} label="Answer citation" />)}
            {reveal.study_progress && <Schedule progress={reveal.study_progress} />}
            {prediction && <ModelComparison prediction={prediction} />}
            {notice && <p className="notice" role="status">{notice}</p>}
            <div className="actions">
              {model && !prediction && <button type="button" disabled={pending} onClick={() => void compareWithModel(reveal)}>Compare with model</button>}
              <button type="button" disabled={pending} onClick={() => void sendFeedback(reveal, false)}>Useful</button>
              <button type="button" disabled={pending} onClick={() => void sendFeedback(reveal, true)}>Report issue</button>
              <button type="button" disabled={pending} onClick={retrySameRound}>Retry same round</button>
              <button type="button" disabled={pending} onClick={() => void loadNextRound()}>Next round</button>
            </div>
          </div>}
        </>}
      </section>}
      {view === "study" && <section aria-labelledby="study-title">
        <h2 id="study-title">Study review</h2>
        {review ? <>
          <Schedule progress={review} />
          <button type="button" onClick={() => void practiceReview(review.round_id)}>Practice this round</button>
        </> : <p>No review is scheduled yet. Finish a practice round to add one.</p>}
      </section>}
    </main>
  );
}

export default App;
