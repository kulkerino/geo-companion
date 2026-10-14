"""Audit the starter pack's visible evidence, answer keys, leakage, and publication gate.

The gazetteer and language tables below are written independently of ``starter_pack`` so the
audit checks the authored answers against a second statement of the facts rather than against
themselves.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ASSET_DIRECTORY = REPOSITORY_ROOT / "apps" / "web" / "public" / "starter-assets"
SVG = "{http://www.w3.org/2000/svg}"

# City -> the only country containing a place of that name at city scale.
GAZETTEER = {
    "BRATISLAVA": "SK",
    "BRNO": "CZ",
    "GRAZ": "AT",
    "DEBRECEN": "HU",
    "KRAKÓW": "PL",
    "LJUBLJANA": "SI",
    "ZAGREB": "HR",
    "CLUJ-NAPOCA": "RO",
    "LEIPZIG": "DE",
    "FIRENZE": "IT",
}
# Municipal-office wording -> countries where that wording is the expected official language.
OFFICE_WORDING = {
    "Mestský úrad": {"SK"},
    "Městský úřad": {"CZ"},
    "Rathaus": {"AT", "DE", "CH"},
    "Polgármesteri Hivatal": {"HU"},
    "Urząd Miasta": {"PL"},
    "Mestna občina": {"SI"},
    "Gradska uprava": {"HR", "BA", "RS", "ME"},
    "Primăria": {"RO", "MD"},
    "Comune": {"IT", "CH", "SM"},
}
# Words that would reveal or narrow a country before the learner answers.
REVEALING_WORDS = {
    "slovakia", "slovak", "slovakian", "czechia", "czech", "austria", "austrian",
    "hungary", "hungarian", "magyar", "poland", "polish", "slovenia", "slovene", "slovenian",
    "croatia", "croatian", "romania", "romanian", "germany", "german", "deutsch", "italy",
    "italian", "switzerland", "swiss", "moldova", "bosnia", "serbia", "serbian",
}  # fmt: skip


def words(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", text.casefold()))


def svg_texts(path: Path) -> list[str]:
    root = ET.parse(path).getroot()
    return ["".join(node.itertext()).strip() for node in root.iter(f"{SVG}text")]


def assert_not_revealing(text: str) -> None:
    from geo_companion.starter_pack import STARTER_DIAGRAMS

    codes = {evidence.country_code.casefold() for evidence in STARTER_DIAGRAMS}
    found = words(text) & (REVEALING_WORDS | codes)
    assert not found, f"{found} in {text!r}"


def test_every_round_has_visible_deterministic_evidence_matching_its_answer() -> None:
    from geo_companion.starter_pack import PRACTICE_ROUNDS, STARTER_DIAGRAMS

    assert len(PRACTICE_ROUNDS) == len(STARTER_DIAGRAMS) == 10
    assert len({evidence.country_code for evidence in STARTER_DIAGRAMS}) == 10
    for evidence, round_ in zip(STARTER_DIAGRAMS, PRACTICE_ROUNDS, strict=True):
        texts = svg_texts(ASSET_DIRECTORY / round_.asset_id)
        assert round_.asset_id == evidence.asset_id
        assert round_.answer.country_code == evidence.country_code

        # The answer is decided by a named place that is actually drawn in the diagram ...
        places = [text for text in texts if text in GAZETTEER]
        assert places == [evidence.place_name]
        assert GAZETTEER[evidence.place_name] == round_.answer.country_code
        # ... and the drawn office wording is consistent with that answer, never contradictory.
        offices = [text for text in texts if text in OFFICE_WORDING]
        assert offices == [evidence.office_phrase]
        assert round_.answer.country_code in OFFICE_WORDING[evidence.office_phrase]

        # The diagram discloses that it is synthetic, not captured imagery.
        assert any("not captured imagery" in text for text in texts)
        # The accessible description states exactly the drawn evidence.
        assert evidence.place_name in round_.asset_description
        assert evidence.office_phrase in round_.asset_description


def test_post_reveal_explanation_names_cue_limitation_and_authored_nature() -> None:
    from geo_companion.contracts import AnswerOrigin
    from geo_companion.starter_pack import PRACTICE_ROUNDS, STARTER_DIAGRAMS

    for evidence, round_ in zip(STARTER_DIAGRAMS, PRACTICE_ROUNDS, strict=True):
        explanation = round_.answer.explanation
        assert round_.answer.answer_origin is AnswerOrigin.AUTHORED
        assert round_.answer.coordinate is None
        assert explanation.startswith(f"Authored teaching target: {evidence.country_name}.")
        assert evidence.place_name in explanation
        assert evidence.office_phrase in explanation
        assert "Limitation:" in explanation
        assert "not a photographed, geolocated" in explanation


def test_public_round_text_and_diagrams_do_not_reveal_any_country() -> None:
    from geo_companion.contracts import PracticeClue, PracticeRoundPublic
    from geo_companion.starter_pack import PRACTICE_ROUNDS

    for round_ in PRACTICE_ROUNDS:
        assert_not_revealing(PracticeRoundPublic.from_round(round_).model_dump_json())
        assert_not_revealing(PracticeClue(round_id=round_.round_id, clue=round_.clue).clue)
        assert_not_revealing((ASSET_DIRECTORY / round_.asset_id).read_text())


def test_diagrams_are_self_contained_and_generated_from_the_authoring_records() -> None:
    for path in sorted(ASSET_DIRECTORY.glob("*.svg")):
        raw = path.read_text()
        root = ET.fromstring(raw)
        tags = {element.tag.removeprefix(SVG) for element in root.iter()}
        attributes = {name for element in root.iter() for name in element.attrib}
        assert not tags & {"script", "image", "foreignObject", "use", "a", "style"}
        assert not any(name.endswith("href") or name.startswith("on") for name in attributes)
        assert "url(" not in raw
        assert re.findall(r"https?://[^\"]+", raw) == ["http://www.w3.org/2000/svg"]

    result = subprocess.run(
        [sys.executable, "packages/api/scripts/generate_starter_diagrams.py", "--check"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_starter_pack_is_cleared_hashed_and_lesson_free() -> None:
    from geo_companion.contracts import RightsStatus
    from geo_companion.starter_pack import PRACTICE_ROUNDS, STARTER_PACK, content_hash

    assert STARTER_PACK.lessons == ()
    assert STARTER_PACK.content_hash == content_hash(PRACTICE_ROUNDS)
    for round_ in STARTER_PACK.practice_rounds:
        for attribution in (round_.asset_attribution, *round_.answer.citations):
            assert attribution.rights_status is RightsStatus.CLEARED
            assert attribution.license_name == "CC0-1.0"
    assert STARTER_PACK.is_publication_ready()
    STARTER_PACK.require_publication_ready()


@pytest.mark.parametrize("status", ["reference-only", "quarantined"])
@pytest.mark.parametrize("target", ["asset", "answer-citation"])
def test_publication_gate_rejects_any_non_cleared_attribution(status: str, target: str) -> None:
    from geo_companion.contracts import (
        Attribution,
        Citation,
        ContentPack,
        PracticeRound,
        PublicationError,
        SourceTruthAnswer,
    )
    from geo_companion.starter_pack import STARTER_PACK

    first = STARTER_PACK.practice_rounds[0]
    weakened = Attribution(**{**first.asset_attribution.model_dump(), "rights_status": status})
    answer = first.answer
    if target == "answer-citation":
        answer = SourceTruthAnswer(
            **{
                **first.answer.model_dump(exclude={"citations"}),
                "citations": (Citation(**weakened.model_dump()),),
            }
        )
        weakened = first.asset_attribution
    round_ = PracticeRound(
        **{
            **first.model_dump(exclude={"asset_attribution", "answer"}),
            "asset_attribution": weakened,
            "answer": answer,
        }
    )
    pack = ContentPack(
        **{
            **STARTER_PACK.model_dump(exclude={"practice_rounds"}),
            "practice_rounds": (round_, *STARTER_PACK.practice_rounds[1:]),
        }
    )

    assert pack.is_publication_ready() is False
    with pytest.raises(PublicationError):
        pack.require_publication_ready()
