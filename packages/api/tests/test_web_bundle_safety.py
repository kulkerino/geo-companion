from __future__ import annotations

import subprocess
from pathlib import Path


def test_production_web_bundle_contains_no_starter_answer_or_synthetic_coordinate() -> None:
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
        asset.read_text() for asset in (repository_root / "apps/web/dist/assets").glob("*.js")
    )
    for forbidden in ("Slovakia", "48.15", "17.11", 'country_code:"SK"'):
        assert forbidden not in bundle
