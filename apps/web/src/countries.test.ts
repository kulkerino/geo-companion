import { describe, expect, it } from "vitest";

import { COUNTRY_CODES, COUNTRY_OPTIONS, country, parseCountryGuess } from "./countries";

describe("countries", () => {
  it("lists only the 109 countries with official GeoGuessr coverage, once each", () => {
    expect(COUNTRY_CODES).toHaveLength(109);
    expect(new Set(COUNTRY_CODES).size).toBe(109);
    expect(COUNTRY_CODES.every((code) => /^[A-Z]{2}$/.test(code))).toBe(true);
    for (const missing of ["CN", "SJ", "AZ", "PW", "AQ"]) expect(COUNTRY_CODES).not.toContain(missing);
    expect(COUNTRY_CODES).toContain("EC");
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
    expect(parseCountryGuess("China")).toBeNull();
    expect(parseCountryGuess("Azerbaijan (AZ)")).toBeNull();
    expect(parseCountryGuess("1")).toBeNull();
  });
});
