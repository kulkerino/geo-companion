// The countries with official GeoGuessr coverage: the only ones the app plays or lets you guess.
// Keep in step with packages/api/src/geo_companion/geoguessr_countries.py (a test checks).
// Names come from the browser's built-in Intl.DisplayNames, so nothing is downloaded. The list
// is the same for every round and never depends on a pack's answers, so it cannot hint at one.
export const COUNTRY_CODES = (
  "AD AE AL AR AS AT AU BD BE BG BM BO BR BT BW CA CH CL CO CR CW CX CZ DE DK DO EC EE ES FI " +
  "FO FR GB GH GI GL GR GT GU HK HR HU ID IE IL IM IN IS IT JE JO JP KE KG KH KR KZ LA LK LS " +
  "LT LU LV MC ME MG MK MN MP MT MX MY NG NL NO NZ PA PE PH PK PL PR PS PT QA RE RO RS RU RW " +
  "SE SG SI SK SM SN SZ TH TN TR TW UA UG UM US UY VI VN ZA"
).split(" ");

const knownCodes = new Set(COUNTRY_CODES);
const regionNames = new Intl.DisplayNames(["en"], { type: "region", fallback: "code" });

function nameOf(code: string) {
  try {
    const name = regionNames.of(code);
    return name && name !== code ? name : undefined;
  } catch {
    return undefined;
  }
}

/** "Slovakia (SK)", or just the code when the browser has no name for it. */
export function country(code: string) {
  const name = nameOf(code);
  return name ? `${name} (${code})` : code;
}

export interface CountryOption {
  code: string;
  label: string;
}

export const COUNTRY_OPTIONS: CountryOption[] = COUNTRY_CODES.map((code) => ({ code, label: country(code) })).sort(
  (a, b) => a.label.localeCompare(b.label, "en"),
);

// Accent- and case-insensitive, so "curacao" finds "Curaçao".
function fold(text: string) {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

const codeByName = new Map(
  COUNTRY_CODES.flatMap((code) => {
    const name = nameOf(code);
    return name ? [[fold(name), code] as const] : [];
  }),
);

/**
 * Turn what the learner typed or picked into a country code, or null if it names no country.
 * Accepts a list entry ("Slovakia (SK)"), a full name ("slovakia") or a code ("sk").
 */
export function parseCountryGuess(text: string): string | null {
  const trimmed = text.trim();
  const fromLabel = /\(([A-Za-z]{2})\)$/.exec(trimmed)?.[1] ?? (/^[A-Za-z]{2}$/.test(trimmed) ? trimmed : undefined);
  if (fromLabel !== undefined) {
    const code = fromLabel.toUpperCase();
    return knownCodes.has(code) ? code : null;
  }
  return codeByName.get(fold(trimmed)) ?? null;
}
