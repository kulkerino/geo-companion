import { useEffect, useState } from "react";

import {
  GeoCompanionApiClient,
  type LessonPublic,
  type LessonsResponse,
  type PracticeAnswerResult,
  type PracticeRoundPublic,
  type QuizAnswerResult,
  type StudyProgress,
} from "./api/generated";
import "./app.css";

const client = new GeoCompanionApiClient();
type View = "knowledge" | "practice" | "study";

function message(error: unknown) {
  return error instanceof Error ? error.message : "The local learning service is unavailable.";
}

function App() {
  const [view, setView] = useState<View>("knowledge");
  const [lessons, setLessons] = useState<LessonsResponse["lessons"]>([]);
  const [lesson, setLesson] = useState<LessonPublic | null>(null);
  const [quizResult, setQuizResult] = useState<QuizAnswerResult | null>(null);
  const [schedule, setSchedule] = useState<StudyProgress | null>(null);
  const [round, setRound] = useState<PracticeRoundPublic | null>(null);
  const [clue, setClue] = useState<string | null>(null);
  const [reveal, setReveal] = useState<PracticeAnswerResult | null>(null);
  const [guess, setGuess] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadLesson = async (lessonId: string) => {
    try {
      setError(null);
      setQuizResult(null);
      setSchedule(null);
      setLesson(await client.get_lesson_api_v1_lessons__lesson_id__get(lessonId));
    } catch (caught) {
      setError(message(caught));
    }
  };

  useEffect(() => {
    void (async () => {
      try {
        const response = await client.list_lessons_api_v1_lessons_get();
        setLessons(response.lessons);
        if (response.lessons[0]) await loadLesson(response.lessons[0].lesson_id);
      } catch (caught) {
        setError(message(caught));
      }
    })();
  }, []);

  const loadRound = async () => {
    try {
      setError(null);
      setClue(null);
      setReveal(null);
      setGuess("");
      setRound(await client.next_practice_round_api_v1_practice_rounds_next_get());
    } catch (caught) {
      setError(message(caught));
    }
  };

  const openPractice = () => {
    setView("practice");
    if (!round || reveal) void loadRound();
  };

  const openStudy = () => {
    setView("study");
    void (async () => {
      try {
        setError(null);
        const review = await client.next_study_review_api_v1_study_review_next_get();
        setSchedule(review.progress ?? null);
      } catch (caught) {
        setError(message(caught));
      }
    })();
  };

  const answerQuiz = async (quizId: string, selectedChoice: string) => {
    if (!lesson) return;
    try {
      setError(null);
      setQuizResult(await client.submit_quiz_answer_api_v1_lessons__lesson_id__quizzes__quiz_id__answers_post(lesson.lesson_id, quizId, { selected_choice: selectedChoice }));
    } catch (caught) {
      setError(message(caught));
    }
  };

  const grade = async (quality: number) => {
    if (!lesson) return;
    try {
      setError(null);
      setSchedule(await client.record_study_grade_api_v1_study_grades_post({ lesson_id: lesson.lesson_id, quality, reviewed_at: new Date().toISOString() }));
    } catch (caught) {
      setError(message(caught));
    }
  };

  const revealClue = async () => {
    if (!round) return;
    try {
      setError(null);
      setClue((await client.get_practice_clue_api_v1_practice_rounds__round_id__clue_get(round.round_id)).clue);
    } catch (caught) {
      setError(message(caught));
    }
  };

  const submitPractice = async (skipped: boolean, uncertain: boolean) => {
    if (!round) return;
    try {
      setError(null);
      const body = skipped ? { skipped: true, uncertain } : { country_code: guess.trim().toUpperCase(), uncertain };
      const answer = await client.submit_practice_answer_api_v1_practice_rounds__round_id__answers_post(round.round_id, body);
      setReveal(answer);
      setSchedule(answer.study_progress ?? null);
    } catch (caught) {
      setError(message(caught));
    }
  };

  const report = async (reportedIssue: boolean) => {
    if (!reveal) return;
    try {
      setError(null);
      await client.submit_feedback_api_v1_feedback_post({ attempt_id: reveal.attempt_id, round_id: reveal.round_id, rating: reportedIssue ? 1 : 4, note: reportedIssue ? "Learner report" : "Useful round", reported_issue: reportedIssue });
      setClue(reportedIssue ? "Report saved locally; it does not replace the authored target." : "Feedback saved locally.");
    } catch (caught) {
      setError(message(caught));
    }
  };

  return (
    <main className="shell">
      <p className="eyebrow">Local learning companion · offline starter pack</p>
      <h1>Geo Companion</h1>
      <nav aria-label="Learning modes" className="tabs">
        <button type="button" onClick={() => setView("knowledge")}>Knowledge</button>
        <button type="button" onClick={openPractice}>Open Practice</button>
        <button type="button" onClick={openStudy}>Study</button>
      </nav>
      {error && <p role="alert">{error}</p>}
      {view === "knowledge" && <section aria-labelledby="knowledge-title">
        <h2 id="knowledge-title">{lesson?.title ?? "Loading lessons…"}</h2>
        {lessons.length > 1 && <label>Choose lesson<select aria-label="Choose lesson" value={lesson?.lesson_id ?? ""} onChange={(event) => void loadLesson(event.target.value)}>{lessons.map((item) => <option key={item.lesson_id} value={item.lesson_id}>{item.title}</option>)}</select></label>}
        {lesson && <><p>{lesson.body}</p><p className="source">{lesson.citations[0]?.attribution_text}</p>{lesson.quiz_items.map((quiz) => <article key={quiz.quiz_id}><h3>{quiz.prompt}</h3>{!quizResult ? quiz.choices.map((choice) => <button className="choice" key={choice} type="button" onClick={() => void answerQuiz(quiz.quiz_id, choice)}>{choice}</button>) : <div className="result"><p>{quizResult.explanation}</p><p className="source">{quizResult.citations[0]?.attribution_text}</p>{[[1, "Again"], [3, "Hard"], [4, "Good"], [5, "Easy"]].map(([quality, label]) => <button key={String(label)} type="button" onClick={() => void grade(Number(quality))}>{label}</button>)}{schedule && <p>Review scheduled in {schedule.interval_days} day.</p>}</div>}</article>)}</>}
      </section>}
      {view === "practice" && <section aria-labelledby="practice-title">
        <h2 id="practice-title">Open Practice</h2>
        {round && <><img className="fixture" src={`/starter-assets/${round.asset_id}`} alt="Original educational country-clue diagram" /><p>{round.asset_attribution.attribution_text}</p>{!reveal ? <><button type="button" onClick={() => void revealClue()}>Reveal optional clue</button>{clue && <p>{clue}</p>}<label htmlFor="guess">Country-code guess</label><input id="guess" value={guess} onChange={(event) => setGuess(event.target.value)} maxLength={2} /><button type="button" disabled={!guess.trim()} onClick={() => void submitPractice(false, false)}>Submit guess</button><button type="button" disabled={!guess.trim()} onClick={() => void submitPractice(false, true)}>Submit uncertain guess</button><button type="button" onClick={() => void submitPractice(true, false)}>Skip</button><button type="button" onClick={() => void submitPractice(true, true)}>Skip as uncertain</button></> : <div className="result"><p>{reveal.answer.explanation}</p><p className="source">Answer origin: {reveal.answer.answer_origin}; separate from learner feedback and corrections.</p><button type="button" onClick={() => void report(false)}>Useful</button><button type="button" onClick={() => void report(true)}>Report issue</button><button type="button" onClick={() => void loadRound()}>Retry / next round</button></div>}</>}
      </section>}
      {view === "study" && <section aria-labelledby="study-title"><h2 id="study-title">Study review</h2><p>{schedule ? `${schedule.lesson_id} is scheduled in ${schedule.interval_days} day.` : "Grade a lesson or finish a practice round to add a local review."}</p></section>}
    </main>
  );
}

export default App;
