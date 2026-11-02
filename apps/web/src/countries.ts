// Offline country list for guesses: ISO 3166-1 alpha-2 codes plus Kosovo (XK, user-assigned).
// Names come from the browser's built-in Intl.DisplayNames, so nothing is downloaded. The list
// is the same for every round and never depends on a pack's answers, so it cannot hint at one.
export const COUNTRY_CODES = (
  "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ " +
  "BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM " +
  "DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS " +
  "GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN " +
  "KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ " +
  "MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM " +
  "PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV " +
  "SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI " +
  "VN VU WF WS XK YE YT ZA ZM ZW"
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
