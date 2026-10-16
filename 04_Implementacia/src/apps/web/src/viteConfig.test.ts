import { describe, expect, it } from "vitest";

import config from "../vite.config";

describe("Vite development server", () => {
  it("binds to loopback and proxies /api to the loopback FastAPI service", () => {
    expect(config.server?.host).toBe("127.0.0.1");
    expect(config.server?.proxy).toEqual({ "/api": "http://127.0.0.1:8000" });
  });
});
