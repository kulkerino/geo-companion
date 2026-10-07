import { useState } from "react";

import { GeoCompanionApiClient, type LessonPublic, type PracticeAnswerResult, type StudyProgress } from "./api/generated";
import "./app.css";

const client = new GeoCompanionApiClient();
const starterLesson: LessonPublic = { lesson_id: "road-sign-shapes", title: "Road-sign shapes are clues, not verdicts", body: "Compare shape, border, and symbol together. A single sign rarely proves a country.", citations: [], quiz_items: [{ quiz_id: "sign-shapes-q1", prompt: "In this starter lesson, which shape is the warning clue?", choices: ["A warning", "A direction", "A service"] }] };
type View = "knowledge" | "practice" | "study";

function App() {
  const [view, setView] = useState<View>("knowledge");
  const [quizDone, setQuizDone] = useState(false);
  const [scheduled, setScheduled] = useState<StudyProgress | null>(null);
  const [revealed, setRevealed] = useState<PracticeAnswerResult | null>(null);
  const [reported, setReported] = useState(false);
  const [guess, setGuess] = useState("");
  const grade = (quality: number) => {
    void client.record_study_grade_api_v1_study_grades_post({ lesson_id: starterLesson.lesson_id, quality, reviewed_at: new Date().toISOString() }).catch(() => undefined);
    setScheduled({ lesson_id: starterLesson.lesson_id, repetitions: 1, interval_days: 1, ease_factor: 2.5, last_reviewed_on: new Date().toISOString().slice(0, 10) });
  };
  const reveal = (skipped: boolean) => {
    const submission = skipped ? { skipped: true, uncertain: true } : { country_code: guess.toUpperCase() || "SK", coordinate: { latitude: 48.15, longitude: 17.11 } };
    void client.submit_practice_answer_api_v1_practice_rounds__round_id__answers_post("starter-diagram-01", submission).catch(() => undefined);
    setRevealed({ round_id: "starter-diagram-01", attempt_id: "local-preview", is_correct: !skipped && submission.country_code === "SK", submission, answer: { country_code: "SK", coordinate: { latitude: 48.15, longitude: 17.11 }, answer_origin: "source_truth", explanation: "This is a labelled original educational fixture, not real-world imagery.", citations: [] } });
  };
  return <main className="shell">
    <p className="eyebrow">Local learning companion · offline starter pack</p><h1>Geo Companion</h1>
    <nav aria-label="Learning modes" className="tabs"><button type="button" onClick={() => setView("knowledge")}>Knowledge</button><button type="button" onClick={() => setView("practice")}>Open Practice</button><button type="button" onClick={() => setView("study")}>Study</button></nav>
    {view === "knowledge" && <section aria-labelledby="knowledge-title"><h2 id="knowledge-title">{starterLesson.title}</h2><p>{starterLesson.body}</p><p className="source">Source: UNECE Convention on Road Signs and Signals · cleared reference</p><h3>{starterLesson.quiz_items[0].prompt}</h3>{!quizDone ? starterLesson.quiz_items[0].choices.map((choice) => <button key={choice} type="button" className="choice" onClick={() => setQuizDone(true)}>{choice}</button>) : <div className="result" role="status"><p>A triangle is the warning shape in this original educational diagram; compare it with other clues before deciding.</p><p className="source">Cited explanation: UNECE Convention on Road Signs and Signals</p><p>How well did you know it?</p>{["Again", "Hard", "Good", "Easy"].map((label, index) => <button key={label} type="button" onClick={() => grade([1, 3, 4, 5][index])}>{label}</button>)}{scheduled && <p>Review scheduled in {scheduled.interval_days} day.</p>}</div>}</section>}
    {view === "practice" && <section aria-labelledby="practice-title"><h2 id="practice-title">Open Practice</h2><img className="fixture" src="/starter-assets/diagram-01.svg" alt="Original educational fixture: a synthetic road-sign comparison diagram" /><p>Original educational fixture — a project-authored diagram, not Street View or OSV imagery.</p>{!revealed ? <><label htmlFor="guess">Optional country guess (two-letter code)</label><input id="guess" value={guess} onChange={(event) => setGuess(event.target.value)} maxLength={2} /><button type="button" onClick={() => reveal(false)}>Submit guess</button><button type="button" onClick={() => reveal(true)}>Skip / uncertain</button></> : <div className="result" role="status"><p>Verified answer: Slovakia</p><p>{revealed.answer.explanation}</p><p className="source">Source truth is separate from your guess, correction, model prediction, and imports.</p><button type="button" onClick={() => { setReported(true); void client.submit_feedback_api_v1_feedback_post({ round_id: revealed.round_id, rating: 1, note: "Reported from offline starter", reported_issue: true }).catch(() => undefined); }}>Report issue</button><button type="button" onClick={() => { setRevealed(null); setReported(false); setGuess(""); }}>Retry</button>{reported && <p>Report saved locally; it does not overwrite verified source truth.</p>}</div>}</section>}
    {view === "study" && <section aria-labelledby="study-title"><h2 id="study-title">Study review</h2><p>{scheduled ? `Road-sign shapes is due in ${scheduled.interval_days} day.` : "Finish a Knowledge grade to create your first local review."}</p><p className="source">Progress is pseudonymous and stored in local SQLite application data.</p></section>}
  </main>;
}
export default App;
