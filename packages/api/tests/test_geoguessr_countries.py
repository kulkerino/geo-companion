from __future__ import annotations

import re
from pathlib import Path

from geo_companion.geoguessr_countries import GEOGUESSR_COUNTRIES, is_geoguessr_country
from geo_companion.starter_pack import PRACTICE_ROUNDS

WEB_LIST = Path(__file__).parents[3] / "apps" / "web" / "src" / "countries.ts"


def test_only_countries_with_official_coverage() -> None:
    assert len(GEOGUESSR_COUNTRIES) == 109
    assert all(re.fullmatch(r"[A-Z]{2}", code) for code in GEOGUESSR_COUNTRIES)
    # The race that started this: only Ecuador of these five is in GeoGuessr.
    assert {"CN", "SJ", "AZ", "PW"}.isdisjoint(GEOGUESSR_COUNTRIES)
    assert is_geoguessr_country("ec") and is_geoguessr_country("SK")


def test_the_web_guess_picker_offers_the_same_countries() -> None:
    block = re.search(r"COUNTRY_CODES = \(([^;]*)\)", WEB_LIST.read_text(encoding="utf-8"))
    assert block is not None
    codes = re.findall(r"\b[A-Z]{2}\b", block.group(1))
    assert len(codes) == len(set(codes))
    assert set(codes) == GEOGUESSR_COUNTRIES


def test_every_starter_round_is_a_geoguessr_country() -> None:
    assert all(is_geoguessr_country(r.answer.country_code) for r in PRACTICE_ROUNDS)
