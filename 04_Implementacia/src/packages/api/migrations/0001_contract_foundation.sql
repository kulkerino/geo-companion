CREATE TABLE content_pack_versions (
    pack_id TEXT NOT NULL,
    version TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (pack_id, version)
);

CREATE TABLE study_progress (
    lesson_id TEXT PRIMARY KEY NOT NULL,
    repetitions INTEGER NOT NULL,
    interval_days INTEGER NOT NULL,
    ease_factor REAL NOT NULL,
    last_reviewed_on TEXT NOT NULL
);

CREATE TABLE practice_attempts (
    attempt_id TEXT PRIMARY KEY NOT NULL,
    round_id TEXT NOT NULL,
    submitted_answer_json TEXT NOT NULL,
    feedback_json TEXT,
    created_at TEXT NOT NULL
);
