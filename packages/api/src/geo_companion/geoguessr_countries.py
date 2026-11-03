"""The countries and territories with official GeoGuessr coverage.

Geo Companion trains for GeoGuessr, so this one list decides which countries the app plays:
photo rounds outside it are dropped at startup, new photo packs only draw from it, the model's
answers are restricted to it, and the web guess picker offers only these. Adding or removing a
country is a one-line change here plus the same change in ``apps/web/src/countries.ts``
(a test keeps the two in step).

Sources (checked 2026-11-02): geohints.com/Country and geometas.com's GeoGuessr country
coverage page. Mainland China is left out on purpose: its few trekker spots are not part of
GeoGuessr's world map.
"""

from __future__ import annotations

GEOGUESSR_COUNTRIES: frozenset[str] = frozenset(
    """
    BW SZ GH KE LS MG NG RE RW SN ZA TN UG
    BD BT KH CX HK IN ID IL JP JO KZ KG LA MY MN PK PH PS QA RU SG KR LK TW TH AE VN
    AL AD AT BE BG HR CZ DK EE FO FI FR DE GI GR HU IS IE IM IT JE LV LT LU MT MC ME NL MK
    NO PL PT RO SM RS SK SI ES SE CH TR UA GB
    BM CA CR CW DO GL GT MX PA PR US VI
    AS AU GU NZ MP UM
    AR BO BR CL CO EC PE UY
    """.split()
)


def is_geoguessr_country(code: str) -> bool:
    return code.upper() in GEOGUESSR_COUNTRIES
