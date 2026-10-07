"""Tiny immutable, offline starter pack of original educational material.

All illustrations are project-authored diagrams, not Street View, OpenStreetCam,
Mapillary, or other captured imagery.  They have intentionally modest geographic
claims and retain a complete provenance record for every claim and asset.
"""
# ruff: noqa: E501

from datetime import UTC, date, datetime

from pydantic import HttpUrl

from geo_companion.contracts import (
    AnswerOrigin,
    Attribution,
    Citation,
    ContentPack,
    Coordinate,
    Lesson,
    PracticeRound,
    QuizItem,
    RightsStatus,
    SourceTruthAnswer,
)

TODAY = date(2026, 10, 7)
LICENSE_URL = HttpUrl("https://creativecommons.org/publicdomain/zero/1.0/")
UNECE_URL = HttpUrl("https://unece.org/transport/road-safety/convention-road-signs-and-signals")


def original_attribution(label: str, scope: str) -> Attribution:
    return Attribution(
        source_title="Geo Companion original educational material",
        source_url=LICENSE_URL,
        creator="Geo Companion project contributors",
        license_name="CC0-1.0",
        license_url=LICENSE_URL,
        attribution_text=f"{label}; original project-authored educational material (not Street View/OSV imagery).",
        accessed_on=TODAY,
        reviewed_on=TODAY,
        geographic_scope=scope,
        rights_status=RightsStatus.CLEARED,
    )


def convention_citation(claim: str) -> Citation:
    return Citation(
        source_title="UNECE Convention on Road Signs and Signals",
        source_url=UNECE_URL,
        creator="United Nations Economic Commission for Europe",
        license_name="Public official document reference",
        license_url=UNECE_URL,
        attribution_text=f"Reference for {claim}; lesson prose is original and intentionally cautious.",
        accessed_on=TODAY,
        reviewed_on=TODAY,
        geographic_scope="International",
        rights_status=RightsStatus.CLEARED,
    )


def original_citation(label: str, scope: str) -> Citation:
    return Citation(**original_attribution(label, scope).model_dump())


LESSONS = (
    Lesson(
        lesson_id="road-sign-shapes",
        title="Road-sign shapes are clues, not verdicts",
        body="Compare shape, border, and symbol together. A single sign rarely proves a country.",
        citations=(convention_citation("standardised road-sign categories"),),
        quiz_items=(
            QuizItem(
                quiz_id="sign-shapes-q1",
                prompt="In this starter lesson, which shape is the warning clue?",
                choices=("A warning", "A direction", "A service"),
                correct_choice="A warning",
                explanation="A triangle is the warning shape in this original educational diagram; compare it with other clues before deciding.",
                citations=(convention_citation("warning-sign categories"),),
            ),
        ),
    ),
    Lesson(
        lesson_id="road-markings",
        title="Read the road, then test the pattern",
        body="Line colour, edge treatment, and driving side are comparative clues. Record uncertainty when evidence conflicts.",
        citations=(convention_citation("road-marking conventions"),),
        quiz_items=(
            QuizItem(
                quiz_id="road-markings-q1",
                prompt="What is the safest use of one road-marking clue?",
                choices=("Form a hypothesis", "Declare a country", "Ignore all other clues"),
                correct_choice="Form a hypothesis",
                explanation="One clue starts a hypothesis; the lesson asks learners to compare several independent signals.",
                citations=(convention_citation("road-marking conventions"),),
            ),
        ),
    ),
    Lesson(
        lesson_id="clue-confidence",
        title="Confidence is part of the answer",
        body="Use skip or uncertain when the evidence is weak. Honest uncertainty produces a better review queue than invented certainty.",
        citations=(original_citation("Original confidence lesson", "Global"),),
        quiz_items=(
            QuizItem(
                quiz_id="clue-confidence-q1",
                prompt="What should you do when the evidence is weak?",
                choices=("Mark uncertain", "Invent precision", "Treat a model as source truth"),
                correct_choice="Mark uncertain",
                explanation="Marking uncertainty preserves the distinction between your observation and verified source truth.",
                citations=(original_citation("Original confidence quiz explanation", "Global"),),
            ),
        ),
    ),
)


def _round(
    index: int, country_code: str, latitude: float, longitude: float, country: str
) -> PracticeRound:
    asset_id = f"diagram-{index:02d}.svg"
    return PracticeRound(
        round_id=f"starter-diagram-{index:02d}",
        asset_id=asset_id,
        asset_attribution=original_attribution(
            f"{asset_id}: original educational diagram fixture", "Synthetic classroom scene"
        ),
        answer=SourceTruthAnswer(
            country_code=country_code,
            coordinate=Coordinate(latitude=latitude, longitude=longitude),
            explanation=f"Verified answer: {country}. This is a labelled original educational fixture, not real-world imagery.",
            citations=(original_citation(f"{asset_id} answer annotation", country),),
            answer_origin=AnswerOrigin.SOURCE_TRUTH,
        ),
    )


PRACTICE_ROUNDS = (
    _round(1, "SK", 48.15, 17.11, "Slovakia"),
    _round(2, "CZ", 50.08, 14.43, "Czechia"),
    _round(3, "AT", 48.21, 16.37, "Austria"),
    _round(4, "HU", 47.50, 19.04, "Hungary"),
    _round(5, "PL", 52.23, 21.01, "Poland"),
    _round(6, "SI", 46.06, 14.51, "Slovenia"),
    _round(7, "HR", 45.81, 15.98, "Croatia"),
    _round(8, "RO", 44.43, 26.10, "Romania"),
    _round(9, "DE", 52.52, 13.41, "Germany"),
    _round(10, "IT", 41.90, 12.50, "Italy"),
)

STARTER_PACK = ContentPack(
    pack_id="starter-original-diagrams",
    version="1.0.0",
    content_hash="sha256:0f741fe00628e31b896d6730dd7e2d21ef00f2b7d9c0e4d771e2d5f1a5d8eacd",
    created_at=datetime(2026, 10, 7, tzinfo=UTC),
    lessons=LESSONS,
    practice_rounds=PRACTICE_ROUNDS,
)
