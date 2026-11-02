from __future__ import annotations

import subprocess
from pathlib import Path


def test_production_web_bundle_contains_no_starter_answer_or_synthetic_coordinate() -> None:
    from geo_companion.starter_pack import STARTER_DIAGRAMS

    repository_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["pnpm", "--dir", "apps/web", "build"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    bundle = "".join(
        asset.read_text(encoding="utf-8")
        for asset in (repository_root / "apps/web/dist/assets").glob("*.js")
    )
    forbidden = ["48.15", "17.11", "Authored teaching target", 'country_code:"']
    for evidence in STARTER_DIAGRAMS:
        forbidden.extend((evidence.country_name, evidence.place_name, evidence.office_phrase))
    for text in forbidden:
        assert text not in bundle, text
