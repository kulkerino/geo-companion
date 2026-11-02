"""Race history and model progress (race mode step 5, see docs/race-mode-plan.md).

The history sums up finished races from the race tables: you against the model, overall and
per model version. Model progress runs the enabled model over a fixed set of photo rounds, so
model versions can be compared on the same photos. The model sees only each public round, as
in a race, and only totals are stored, so nothing here reveals a round's answer.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from geo_companion.contracts import (
    ModelBenchmarkRun,
    ModelBenchmarks,
    ModelInfo,
    RaceHistory,
    RaceHistoryEntry,
    RaceModelRecord,
    RaceScore,
    RaceTally,
)
from geo_companion.race import RaceService, RaceUnavailableError


def photo_set_id(round_ids: list[str]) -> str:
    """A short stable name for a set of rounds; the same rounds always give the same id."""
    digest = hashlib.sha256("\n".join(sorted(round_ids)).encode()).hexdigest()
    return f"photos-{len(round_ids)}-{digest[:12]}"


def _tally(entries: list[RaceHistoryEntry]) -> RaceTally:
    return RaceTally(
        races=len(entries),
        rounds=sum(entry.rounds_total for entry in entries),
        learner_points=sum(entry.score.learner for entry in entries),
        model_points=sum(entry.score.model for entry in entries),
        learner_wins=sum(entry.score.learner > entry.score.model for entry in entries),
        model_wins=sum(entry.score.learner < entry.score.model for entry in entries),
        draws=sum(entry.score.learner == entry.score.model for entry in entries),
    )


class RaceHistoryService:
    def __init__(
        self, races: RaceService, *, now: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.races = races
        self.learning = races.learning
        self.now = now
        with self.learning._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS model_benchmarks ("
                "model_json TEXT NOT NULL, photo_set_id TEXT NOT NULL, rounds INTEGER NOT NULL, "
                "correct INTEGER NOT NULL, abstained INTEGER NOT NULL, failed INTEGER NOT NULL, "
                "created_at TEXT NOT NULL, PRIMARY KEY (model_json, photo_set_id))"
            )

    def history(self) -> RaceHistory:
        with self.learning._connect() as connection:
            races = connection.execute(
                "SELECT races.*, SUM(race_rounds.learner_points) AS learner, "
                "SUM(race_rounds.model_points) AS model, COUNT(*) AS rounds_total "
                "FROM races JOIN race_rounds USING (race_id) "
                "WHERE races.learner_id = ? AND races.finished_at IS NOT NULL "
                "AND races.player = 'you' "  # class (projector) races are not your record
                "GROUP BY races.race_id ORDER BY races.created_at DESC, races.rowid DESC",
                (self.learning.learner_id,),
            ).fetchall()
        entries = [self._entry(race) for race in races]
        by_model: dict[ModelInfo, list[RaceHistoryEntry]] = {}
        for entry in reversed(entries):  # oldest first, so models appear in the order raced
            by_model.setdefault(entry.model, []).append(entry)
        return RaceHistory(
            races=tuple(entries),
            overall=_tally(entries),
            by_model=tuple(
                RaceModelRecord(model=model, tally=_tally(model_entries))
                for model, model_entries in by_model.items()
            ),
        )

    @staticmethod
    def _entry(race: sqlite3.Row) -> RaceHistoryEntry:
        return RaceHistoryEntry(
            race_id=race["race_id"],
            model=ModelInfo.model_validate_json(race["model_json"]),
            time_limit_seconds=race["time_limit_seconds"],
            created_at=datetime.fromisoformat(race["created_at"]),
            finished_at=datetime.fromisoformat(race["finished_at"]),
            score=RaceScore(learner=race["learner"] or 0, model=race["model"] or 0),
            rounds_total=race["rounds_total"],
        )

    def _photo_set(self) -> tuple[list[str], str | None]:
        round_ids = sorted(self.races._photo_round_ids())
        return round_ids, photo_set_id(round_ids) if round_ids else None

    def benchmarks(self) -> ModelBenchmarks:
        round_ids, set_id = self._photo_set()
        with self.learning._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_benchmarks ORDER BY created_at, rowid"
            ).fetchall()
        reason = self.races.unavailable_reason()
        return ModelBenchmarks(
            photo_set_id=set_id,
            photo_rounds=len(round_ids),
            runs=tuple(self._run(row) for row in rows),
            can_run=reason is None,
            reason=reason,
        )

    @staticmethod
    def _run(row: sqlite3.Row) -> ModelBenchmarkRun:
        return ModelBenchmarkRun(
            model=ModelInfo.model_validate_json(row["model_json"]),
            photo_set_id=row["photo_set_id"],
            rounds=row["rounds"],
            correct=row["correct"],
            abstained=row["abstained"],
            failed=row["failed"],
            accuracy=row["correct"] / row["rounds"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def run_benchmark(self) -> ModelBenchmarkRun:
        """Let the enabled model guess every photo of the fixed set and store the totals.

        The model is deterministic, so a model version is run once per photo set; asking again
        returns the stored run.
        """
        reason = self.races.unavailable_reason()
        if reason is not None:
            raise RaceUnavailableError(reason)
        provider = self.learning.provider
        assert provider is not None
        round_ids, set_id = self._photo_set()
        assert set_id is not None
        model_json = provider.info.model_dump_json()
        with self.learning._connect() as connection:
            stored = connection.execute(
                "SELECT * FROM model_benchmarks WHERE model_json = ? AND photo_set_id = ?",
                (model_json, set_id),
            ).fetchone()
        if stored is not None:
            return self._run(stored)
        correct = abstained = failed = 0
        for round_id in round_ids:
            try:
                candidates = provider.predict(self.learning.round_public(round_id))
            except Exception:  # noqa: BLE001 - a failed photo scores nothing, as in a race
                failed += 1
                continue
            if not candidates:
                abstained += 1
            elif candidates[0].country_code == self.learning._round(round_id).answer.country_code:
                correct += 1
        created_at = self.now().isoformat()
        with self.learning._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO model_benchmarks (model_json, photo_set_id, rounds, "
                "correct, abstained, failed, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (model_json, set_id, len(round_ids), correct, abstained, failed, created_at),
            )
            row = connection.execute(
                "SELECT * FROM model_benchmarks WHERE model_json = ? AND photo_set_id = ?",
                (model_json, set_id),
            ).fetchone()
        return self._run(row)
