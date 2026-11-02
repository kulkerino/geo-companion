import { useEffect, useState, type ChangeEvent } from "react";

import {
  GeoCompanionApiClient,
  type ModelCandidate,
  type ModelEvaluation,
  type ModelInfo,
  type ModelPredictionResult,
  type PhotoGuessResult,
  type PracticeAnswerResult,
  type PracticeRoundPublic,
  type StudyProgress,
} from "./api/generated";
import "./app.css";
import { AttributionDetails } from "./AttributionDetails";
import { COUNTRY_OPTIONS, country, parseCountryGuess } from "./countries";
import { RaceMode } from "./Race";

const client = new GeoCompanionApiClient();
type View = "practice" | "study" | "photo" | "accuracy" | "race";
const PHOTO_TYPES = "image/jpeg,image/png,image/webp";

function message(error: unknown) {
  return error instanceof Error ? error.message : "The local learning service is unavailable.";
}

function days(count: number) {
  return `${count} ${count === 1 ? "day" : "days"}`;
}

// Diagrams ship with the web app; photos come from the local photo pack through the API.
function assetUrl(round: PracticeRoundPublic) {
  const id = encodeURIComponent(round.asset_id);
  return round.asset_kind === "photo" ? `/api/v1/assets/${id}` : `/starter-assets/${id}`;
}

function Schedule({ progress }: { progress: StudyProgress }) {
  return (
    <p>
      Next review of {progress.round_id} on {progress.next_review_on} (interval {days(progress.interval_days)}, ease {progress.ease_factor}).
    </p>
  );
}

function ModelOpinion({ label, model, candidates, abstained, note }: { label: string; model: ModelInfo; candidates: ModelCandidate[]; abstained: boolean; note: string }) {
  return (
    <div className="model" aria-label={label}>
      <p className="model-name">
        Model opinion: {model.model_id} {model.version}{model.is_placeholder ? " (placeholder, not real inference)" : ""}
      </p>
      <p className="origin">{model.description}</p>
      {abstained ? <p>The model abstained: it was not confident enough to guess.</p> : (
        <ol>
          {candidates.map((candidate) => <li key={candidate.country_code}>{country(candidate.country_code)} · {Math.round(candidate.confidence * 100)}%</li>)}
        </ol>
      )}
      <p className="origin">{note}</p>
    </div>
  );
}

function ModelComparison({ prediction }: { prediction: ModelPredictionResult }) {
  return <ModelOpinion label="Model comparison" model={prediction.model} candidates={prediction.candidates} abstained={prediction.abstained} note="Model output is stored separately and never changes the authored answer." />;
}

// The learner's own photo goes only to the local API, which keeps it in memory for one request.
function PhotoGuess({ model }: { model: ModelInfo | null }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<PhotoGuessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const choose = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    setPreview(chosen ? URL.createObjectURL(chosen) : null);
    setResult(null);
    setError(null);
  };

  const ask = async () => {
    if (!file) return;
    try {
      setPending(true);
      setError(null);
      setResult(await client.guess_photo_api_v1_photo_guesses_post(file));
    } catch (caught) {
      setError(message(caught));
    } finally {
      setPending(false);
    }
  };

  return (
    <section aria-labelledby="photo-title">
      <h2 id="photo-title">Your photo</h2>
      <p>Choose a street-level photo of your own. The model gives its top three country guesses, or abstains when it is not sure. It is a guess, not an identification.</p>
      <p className="origin">The photo stays on this computer: it is sent only to the local service, used for this one guess, and never saved.</p>
      {!model && <p>No local model is enabled, so there is nothing to ask yet.</p>}
      <label htmlFor="photo-file">Photo (JPEG, PNG or WebP)</label>
      <input id="photo-file" type="file" accept={PHOTO_TYPES} onChange={choose} />
      {preview && <img className="fixture photo" src={preview} alt="Your chosen photo" />}
      {error && <p role="alert">{error}</p>}
      <div className="actions">
        <button type="button" disabled={pending || !file || !model} onClick={() => void ask()}>Ask the model</button>
      </div>
      {result && <ModelOpinion label="Model guess for your photo" model={result.model} candidates={result.candidates} abstained={result.abstained} note="Your photo has no known answer, so this guess is not graded and is not saved." />}
    </section>
  );
}

function percent(rate: number) {
  return `${(rate * 100).toFixed(1)}%`;
}

// Read-only results recorded when the model was trained; nothing here touches learner data.
function ModelAccuracy({ model }: { model: ModelInfo | null }) {
  const [evaluation, setEvaluation] = useState<ModelEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!model) return;
    client.model_evaluation_api_v1_models_evaluation_get().then(setEvaluation, (caught: unknown) => setError(message(caught)));
  }, [model]);

  const rows = evaluation ? [...(evaluation.per_country ?? [])].sort((a, b) => b.top1 - a.top1 || a.country_code.localeCompare(b.country_code)) : [];
  const splitName = evaluation?.split === "test" ? "held-out test photos" : evaluation?.split === "val" ? "validation photos" : "evaluation photos";

  return (
    <section aria-labelledby="accuracy-title">
      <h2 id="accuracy-title">Model accuracy</h2>
      {!model && <p>No local model is enabled, so there are no results to show.</p>}
      {model && !evaluation && !error && <p>Loading the model's results…</p>}
      {error && <p role="alert">{error}</p>}
      {evaluation && <>
        <p className="model-name">{evaluation.model.model_id} {evaluation.model.version}</p>
        <p>
          Measured once, after training, on {evaluation.images.toLocaleString("en")} {splitName} from {evaluation.classes} countries
          {evaluation.out_of_label_set > 0 && ` (${evaluation.out_of_label_set.toLocaleString("en")} more photos come from countries the model was not trained on and are not counted)`}.
        </p>
        <dl className="source" aria-label="Accuracy summary">
          <dt>Right country first</dt>
          <dd>{percent(evaluation.top1)} (top-1)</dd>
          <dt>Right country in top 5</dt>
          <dd>{percent(evaluation.top5)}</dd>
          <dt>Always guessing {country(evaluation.baselines.majority_class)}</dt>
          <dd>{percent(evaluation.baselines.majority_top1)}</dd>
          <dt>Guessing at random</dt>
          <dd>{percent(evaluation.baselines.uniform_top1)}</dd>
          <dt>Photos it answers</dt>
          <dd>{percent(evaluation.abstention.coverage)}; it abstains on the rest</dd>
          <dt>Right when it answers</dt>
          <dd>{evaluation.abstention.selective_top1 == null ? "it never answers" : percent(evaluation.abstention.selective_top1)}</dd>
          <dt>Calibration error</dt>
          <dd>{percent(evaluation.ece_raw)} before, {percent(evaluation.ece_calibrated)} after calibration (lower is better)</dd>
        </dl>
        <p className="origin">These are past results on photos the model never trained on. They describe the model, not any single guess, and they never change an authored answer.</p>
        {rows.length > 0 ? <table className="accuracy">
          <caption>Top-1 accuracy by country (countries with enough test photos)</caption>
          <thead><tr><th scope="col">Country</th><th scope="col">Photos</th><th scope="col">Top-1</th></tr></thead>
          <tbody>
            {rows.map((row) => <tr key={row.country_code}>
              <th scope="row">{country(row.country_code)}</th>
              <td>{row.images.toLocaleString("en")}</td>
              <td><span className="bar" style={{ width: `${row.top1 * 6}rem` }} aria-hidden="true" /> {percent(row.top1)}</td>
            </tr>)}
          </tbody>
        </table> : <p>No per-country results were recorded for this model.</p>}
        <p className="origin">Trained on {evaluation.trained_on} ({evaluation.dataset_license}). {evaluation.dataset_attribution}</p>
      </>}
    </section>
  );
}

function outcome(reveal: PracticeAnswerResult) {
  if (reveal.submission.skipped) return "Skipped.";
  const confidence = reveal.submission.uncertain ? " (marked uncertain)" : "";
  return reveal.is_correct
    ? `Correct${confidence}.`
    : `Not correct${confidence}: you guessed ${reveal.submission.country_code ? country(reveal.submission.country_code) : "nothing"}.`;
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

  const guessCode = parseCountryGuess(guess);
  const validGuess = guessCode !== null;

  const submitPractice = (roundId: string, skipped: boolean, uncertain: boolean) => run(async () => {
    const body = skipped ? { skipped: true, uncertain } : { country_code: guessCode ?? undefined, uncertain };
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


  return (
    <main className="shell">
      <p className="eyebrow">Local learning companion · offline practice</p>
      <h1>Geo Companion</h1>
      <nav aria-label="Learning modes" className="tabs">
        <button type="button" aria-pressed={view === "practice"} onClick={openPractice}>Open Practice</button>
        <button type="button" aria-pressed={view === "study"} onClick={openStudy}>Study review</button>
        <button type="button" aria-pressed={view === "photo"} onClick={() => setView("photo")}>Your photo</button>
        <button type="button" aria-pressed={view === "accuracy"} onClick={() => setView("accuracy")}>Model accuracy</button>
        <button type="button" aria-pressed={view === "race"} onClick={() => setView("race")}>Race the model</button>
      </nav>
      {error && (view === "practice" || view === "study") && <p role="alert">{error}</p>}
      {view === "photo" && <PhotoGuess model={model} />}
      {view === "accuracy" && <ModelAccuracy model={model} />}
      {view === "race" && <RaceMode />}
      {view === "practice" && <section aria-labelledby="practice-title">
        <h2 id="practice-title">Open Practice</h2>
        {!round && !error && <p>Loading a practice round…</p>}
        {round && <>
          <p className="round-id">Round {round.round_id}</p>
          <img className={round.asset_kind === "photo" ? "fixture photo" : "fixture"} src={assetUrl(round)} alt={round.asset_description} />
          <AttributionDetails attribution={round.asset_attribution} label={round.asset_kind === "photo" ? "Photo attribution" : "Diagram attribution"} />
          {!reveal ? <div className="attempt">
            <button type="button" onClick={() => void revealClue(round.round_id)}>Reveal optional clue</button>
            {clue && <p className="clue">{clue}</p>}
            <label htmlFor="guess">Country guess (type to search, e.g. France or FR)</label>
            <input id="guess" list="country-options" value={guess} onChange={(event) => setGuess(event.target.value)} autoComplete="off" />
            <datalist id="country-options">
              {COUNTRY_OPTIONS.map((option) => <option key={option.code} value={option.label} />)}
            </datalist>
            {guess.trim() && !validGuess && <p className="origin">Pick a country from the list, or type its full name or two-letter code.</p>}
            <div className="actions">
              <button type="button" disabled={pending || !validGuess} onClick={() => void submitPractice(round.round_id, false, false)}>Submit guess</button>
              <button type="button" disabled={pending || !validGuess} onClick={() => void submitPractice(round.round_id, false, true)}>Submit uncertain guess</button>
              <button type="button" disabled={pending} onClick={() => void submitPractice(round.round_id, true, false)}>Skip</button>
            </div>
          </div> : <div className="result">
            <p className="outcome">{outcome(reveal)}</p>
            <p>Answer: <strong>{country(reveal.answer.country_code)}</strong></p>
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
