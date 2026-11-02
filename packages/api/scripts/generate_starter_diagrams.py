"""Render the starter-pack Open Practice SVGs deterministically from their authoring records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "api" / "src"))

from geo_companion.starter_pack import STARTER_DIAGRAMS, DiagramEvidence  # noqa: E402

ASSET_DIRECTORY = REPOSITORY_ROOT / "apps" / "web" / "public" / "starter-assets"
DISCLAIMER = "Synthetic teaching diagram — not captured imagery or an official sign design"


def render(evidence: DiagramEvidence) -> str:
    """Draw a schematic place-name panel and municipal-office panel; no external references."""
    place_size = 44 if len(evidence.place_name) <= 9 else 34
    phrase = evidence.office_phrase
    if len(phrase) <= 12:
        office_text = (
            '  <text x="494" y="203" font-size="24" fill="#1f2328" text-anchor="middle">'
            f"{escape(phrase)}</text>\n"
        )
    else:
        # Long phrases wrap at the last space; the trailing space keeps the joined text exact.
        first, second = phrase.rsplit(" ", maxsplit=1)
        office_text = (
            '  <text font-size="22" fill="#1f2328" text-anchor="middle">'
            f'<tspan x="494" y="190">{escape(first)} </tspan>'
            f'<tspan x="494" y="216">{escape(second)}</tspan></text>\n'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" '
        'viewBox="0 0 640 360" font-family="DejaVu Sans, Arial, sans-serif">\n'
        '  <rect width="640" height="360" fill="#e9f0f4"/>\n'
        '  <path d="M0 318H640" stroke="#5b6168" stroke-width="56"/>\n'
        '  <path d="M20 318H620" stroke="#f4f4f4" stroke-width="4" stroke-dasharray="28 20"/>\n'
        '  <rect x="128" y="190" width="10" height="100" fill="#6b6f74"/>\n'
        '  <rect x="22" y="96" width="320" height="96" rx="6" fill="#ffffff" stroke="#1f2328"'
        ' stroke-width="6"/>\n'
        f'  <text x="182" y="160" font-size="{place_size}" font-weight="700" fill="#1f2328"'
        f' text-anchor="middle">{escape(evidence.place_name)}</text>\n'
        '  <text x="182" y="88" font-size="14" fill="#3b4148" text-anchor="middle">'
        "place-name panel</text>\n"
        '  <path d="M380 290V150L494 92L608 150V290Z" fill="#f3ede1" stroke="#6b5b45"'
        ' stroke-width="4"/>\n'
        '  <rect x="398" y="168" width="192" height="54" rx="4" fill="#ffffff" stroke="#6b5b45"'
        ' stroke-width="3"/>\n'
        f"{office_text}"
        '  <rect x="474" y="236" width="40" height="54" fill="#8a7a63"/>\n'
        '  <text x="494" y="84" font-size="14" fill="#3b4148" text-anchor="middle">'
        "municipal-office panel</text>\n"
        f'  <text x="20" y="32" font-size="16" fill="#1f2328">Original practice diagram'
        f" {evidence.index:02d}</text>\n"
        f'  <text x="20" y="54" font-size="13" fill="#3b4148">{escape(DISCLAIMER)}</text>\n'
        "</svg>\n"
    )


def generated_files() -> dict[Path, str]:
    return {ASSET_DIRECTORY / evidence.asset_id: render(evidence) for evidence in STARTER_DIAGRAMS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail when committed diagrams drift or extras exist"
    )
    args = parser.parse_args()
    files = generated_files()
    if args.check:
        stale = [
            path
            for path, text in files.items()
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        extra = sorted(set(ASSET_DIRECTORY.glob("*.svg")) - set(files))
        if stale or extra:
            print("Starter diagrams are stale or unexpected:")
            print("\n".join(str(path.relative_to(REPOSITORY_ROOT)) for path in (*stale, *extra)))
            return 1
        return 0
    ASSET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path, contents in files.items():
        path.write_text(contents, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
