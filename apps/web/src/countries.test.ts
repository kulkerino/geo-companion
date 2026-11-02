import { describe, expect, it } from "vitest";

import { COUNTRY_CODES, COUNTRY_OPTIONS, country, parseCountryGuess } from "./countries";

describe("countries", () => {
  it("lists every ISO 3166-1 alpha-2 code plus Kosovo, once each", () => {
    expect(COUNTRY_CODES).toHaveLength(250);
    expect(new Set(COUNTRY_CODES).size).toBe(250);
    expect(COUNTRY_CODES.every((code) => /^[A-Z]{2}$/.test(code))).toBe(true);
    expect(COUNTRY_CODES).toContain("XK");
  });

  it("offers every country as 'Name (CODE)', sorted by name", () => {
    expect(COUNTRY_OPTIONS).toHaveLength(COUNTRY_CODES.length);
    expect(COUNTRY_OPTIONS.find((option) => option.code === "SK")?.label).toBe("Slovakia (SK)");
    const labels = COUNTRY_OPTIONS.map((option) => option.label);
    expect(labels).toEqual([...labels].sort((a, b) => a.localeCompare(b, "en")));
  });

  it("reads a picked entry, a typed name or a typed code", () => {
    expect(parseCountryGuess("Slovakia (SK)")).toBe("SK");
    expect(parseCountryGuess("  slovakia ")).toBe("SK");
    expect(parseCountryGuess("sk")).toBe("SK");
    expect(parseCountryGuess("curacao")).toBe("CW");
    expect(parseCountryGuess(country("CZ"))).toBe("CZ");
  });

  it("rejects text that names no country", () => {
    expect(parseCountryGuess("")).toBeNull();
    expect(parseCountryGuess("Slov")).toBeNull();
    expect(parseCountryGuess("ZZ")).toBeNull();
    expect(parseCountryGuess("Narnia (ZZ)")).toBeNull();
    expect(parseCountryGuess("1")).toBeNull();
  });
});
