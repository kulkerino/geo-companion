"""Tiny immutable, offline starter pack of original Open Practice diagrams.

Every illustration is a project-authored schematic diagram, not Street View, OpenStreetCam,
Mapillary, or other captured imagery. Each round's answer is an authored teaching target whose
evidence is visible text in the diagram: a place-name panel naming a city that exists in only one
country, plus a municipal-office panel whose language agrees with it. The SVG files are rendered
deterministically from ``STARTER_DIAGRAMS`` by ``packages/api/scripts/generate_starter_diagrams.py``.
"""
# ruff: noqa: E501

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pydantic import HttpUrl

from geo_companion.contracts import (
    AnswerOrigin,
    Attribution,
    Citation,
    ContentPack,
    PracticeRound,
    RightsStatus,
    SourceTruthAnswer,
)

AUTHORED_ON = date(2026, 10, 14)
CC0_URL = HttpUrl("https://creativecommons.org/publicdomain/zero/1.0/")

# Deliberately generic: it names the evidence types to inspect, never a country, code, or language.
CLUE = "Read both panels: which country contains the named place, and does the office wording agree?"


@dataclass(frozen=True)
class DiagramEvidence:
    """Authoring record for one diagram; the answer fields never reach a pre-answer payload."""

    index: int
    country_code: str
    country_name: str
    place_name: str
    office_phrase: str
    language: str
    limitation: str

    @property
    def round_id(self) -> str:
        return f"starter-place-{self.index:02d}"

    @property
    def asset_id(self) -> str:
        return f"place-panel-{self.index:02d}.svg"


STARTER_DIAGRAMS = (
    DiagramEvidence(1, "SK", "Slovakia", "BRATISLAVA", "Mestský úrad", "Slovak",
                    "the office wording alone is close to Czech; Czech spells it “Městský úřad”, so the place name decides."),
    DiagramEvidence(2, "CZ", "Czechia", "BRNO", "Městský úřad", "Czech",
                    "Slovak uses very similar words, but “ř” and “ě” are Czech spellings; the place name still decides."),
    DiagramEvidence(3, "AT", "Austria", "GRAZ", "Rathaus", "German",
                    "“Rathaus” is equally at home in Germany and Switzerland; only the place name separates them."),
    DiagramEvidence(4, "HU", "Hungary", "DEBRECEN", "Polgármesteri Hivatal", "Hungarian",
                    "Hungarian is also a minority language in neighbouring countries, so the wording alone is not a verdict."),
    DiagramEvidence(5, "PL", "Poland", "KRAKÓW", "Urząd Miasta", "Polish",
                    "the letter “ą” narrows the language, not the exact location; the place name decides."),
    DiagramEvidence(6, "SI", "Slovenia", "LJUBLJANA", "Mestna občina", "Slovene",
                    "“č” is shared by several Slavic languages, so the wording alone could mislead without the place name."),
    DiagramEvidence(7, "HR", "Croatia", "ZAGREB", "Gradska uprava", "Croatian",
                    "very similar wording appears in Bosnian and Serbian Latin-script contexts; the place name decides."),
    DiagramEvidence(8, "RO", "Romania", "CLUJ-NAPOCA", "Primăria", "Romanian",
                    "Romanian is also official in Moldova, so the wording narrows the language but not the country."),
    DiagramEvidence(9, "DE", "Germany", "LEIPZIG", "Rathaus", "German",
                    "the same office word appears in Austria and Switzerland; compare this round with the GRAZ round."),
    DiagramEvidence(10, "IT", "Italy", "FIRENZE", "Comune", "Italian",
                    "Italian is also official in Switzerland and San Marino, so the wording alone is not a verdict."),
)


def original_attribution(label: str, scope: str) -> Attribution:
    return Attribution(
        source_title="Geo Companion original educational material",
        source_url=CC0_URL,
        creator="Geo Companion project contributors",
        license_name="CC0-1.0",
        license_url=CC0_URL,
        attribution_text=f"{label}; original project-authored schematic diagram, not Street View or other captured imagery.",
        accessed_on=AUTHORED_ON,
        reviewed_on=AUTHORED_ON,
        geographic_scope=scope,
        rights_status=RightsStatus.CLEARED,
    )


def asset_description(evidence: DiagramEvidence) -> str:
    return (
        f"Synthetic schematic diagram: a place-name panel reading {evidence.place_name} "
        f"beside a municipal-office panel reading “{evidence.office_phrase}”."
    )


def answer_explanation(evidence: DiagramEvidence) -> str:
    return (
        f"Authored teaching target: {evidence.country_name}. "
        f"Cue: the place-name panel reads {evidence.place_name}, a city in {evidence.country_name}, "
        f"and the office wording “{evidence.office_phrase}” is {evidence.language}, which agrees. "
        f"Limitation: {evidence.limitation[0].upper()}{evidence.limitation[1:]} "
        "This is an original synthetic diagram with schematic sign styling, not a photographed, "
        "geolocated, or official national sign design."
    )


def _round(evidence: DiagramEvidence) -> PracticeRound:
    return PracticeRound(
        round_id=evidence.round_id,
        asset_id=evidence.asset_id,
        asset_attribution=original_attribution(
            f"{evidence.asset_id}: original Open Practice diagram", "Synthetic classroom scene"
        ),
        asset_description=asset_description(evidence),
        clue=CLUE,
        answer=SourceTruthAnswer(
            country_code=evidence.country_code,
            explanation=answer_explanation(evidence),
            citations=(
                Citation(
                    **original_attribution(
                        f"{evidence.asset_id} authored answer annotation", evidence.country_name
                    ).model_dump()
                ),
            ),
            answer_origin=AnswerOrigin.AUTHORED,
        ),
    )


PRACTICE_ROUNDS = tuple(_round(evidence) for evidence in STARTER_DIAGRAMS)


def content_hash(rounds: tuple[PracticeRound, ...]) -> str:
    """Hash the canonical pack content so the version identity is not a hand-typed constant."""
    canonical = json.dumps(
        [round_.model_dump(mode="json") for round_ in rounds],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


STARTER_PACK = ContentPack(
    pack_id="starter-original-diagrams",
    version="2.0.0",
    content_hash=content_hash(PRACTICE_ROUNDS),
    created_at=datetime(2026, 10, 14, tzinfo=UTC),
    lessons=(),
    practice_rounds=PRACTICE_ROUNDS,
)
