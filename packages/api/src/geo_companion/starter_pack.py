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
        rights_status=RightsStatus.REFERENCE_ONLY,
    )


def original_citation(label: str, scope: str) -> Citation:
    return Citation(**original_attribution(label, scope).model_dump())


LESSONS = (
    Lesson(
        lesson_id="road-sign-shapes",
        title="Road-sign shapes are clues, not verdicts",
        body=(
            "Start with the whole sign system: shape, border, colour, symbol, and nearby language. "
            "The diagram compares a warning triangle with a service panel. A triangle can support a "
            "hypothesis, but it is shared across many countries, so it is never a country verdict. "
            "Counterexample: identical warning geometry appears across multiple Convention sign systems."
        ),
        diagram_asset_id="diagram-01.svg",
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
        body=(
            "Road paint is most useful as a comparison exercise. Notice the centre line, the edge line, "
            "and whether a sign, language clue, or lane direction agrees. Record uncertainty when clues "
            "conflict: resurfacing and local road works make markings weak evidence. Compare at least two "
            "independent observations before choosing a country."
        ),
        diagram_asset_id="diagram-04.svg",
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
        body=(
            "Confidence is evidence too. Mark a guess uncertain when the clue could fit multiple countries, "
            "and skip when there is no defensible hypothesis. The comparison diagram deliberately includes "
            "an ambiguous exit word: a language fragment may narrow a region without identifying one country. "
            "Honest uncertainty creates a useful review queue instead of invented precision."
        ),
        diagram_asset_id="diagram-10.svg",
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


def _round(index: int, country_code: str, country: str, clue: str) -> PracticeRound:
    asset_id = f"diagram-{index:02d}.svg"
    return PracticeRound(
        round_id=f"starter-diagram-{index:02d}",
        asset_id=asset_id,
        asset_attribution=original_attribution(
            f"{asset_id}: original educational diagram fixture", "Synthetic classroom scene"
        ),
        clue=clue,
        answer=SourceTruthAnswer(
            country_code=country_code,
            explanation=(
                f"Teaching target: {country}. This is an authored country-clue diagram, "
                "not a photographed or geolocated scene."
            ),
            citations=(original_citation(f"{asset_id} answer annotation", country),),
            answer_origin=AnswerOrigin.AUTHORED,
        ),
    )


PRACTICE_ROUNDS = (
    _round(
        1, "SK", "Slovakia", "Compare the Slovak-looking exit word with neighbouring languages."
    ),
    _round(
        2, "CZ", "Czechia", "Check the Czech diacritic before using the word as a country clue."
    ),
    _round(3, "AT", "Austria", "German is shared: the diagram needs a second road-system clue."),
    _round(
        4,
        "HU",
        "Hungary",
        "The accented Hungarian word is the strongest clue in this authored example.",
    ),
    _round(5, "PL", "Poland", "The Polish warning word contains a distinctive letter pattern."),
    _round(
        6, "SI", "Slovenia", "Treat the Slovenian exit word as a language clue, not a location."
    ),
    _round(7, "HR", "Croatia", "Compare this South Slavic exit word with the Slovenian version."),
    _round(
        8,
        "RO",
        "Romania",
        "The Romanian exit word is presented as an authored language comparison.",
    ),
    _round(
        9,
        "DE",
        "Germany",
        "German-language signage alone cannot distinguish every German-speaking country.",
    ),
    _round(
        10,
        "IT",
        "Italy",
        "The Italian exit word is a clue that should be cross-checked with road markings.",
    ),
)

STARTER_PACK = ContentPack(
    pack_id="starter-original-diagrams",
    version="1.0.0",
    content_hash="sha256:0f741fe00628e31b896d6730dd7e2d21ef00f2b7d9c0e4d771e2d5f1a5d8eacd",
    created_at=datetime(2026, 10, 7, tzinfo=UTC),
    lessons=LESSONS,
    practice_rounds=PRACTICE_ROUNDS,
)
