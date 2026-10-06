// @vitest-environment node
import { afterEach, describe, expect, test, vi } from "vitest";

import nextConfig from "./next.config";

async function regrasDeRewrite() {
  const regras = await nextConfig.rewrites!();
  if (!Array.isArray(regras)) throw new Error("rewrites deveria devolver uma lista");
  return regras;
}

describe("rewrite de /api para a API (ADR-006)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  test("reescreve /api/* para a URL de API_URL, mantendo o caminho", async () => {
    vi.stubEnv("API_URL", "https://api.exemplo.test/");

    expect(await regrasDeRewrite()).toEqual([
      { source: "/api/:path*", destination: "https://api.exemplo.test/api/:path*" },
    ]);
  });

  test("sem API_URL falha, em vez de usar um endereço fixo no código", async () => {
    vi.stubEnv("API_URL", "");

    await expect(regrasDeRewrite()).rejects.toThrow("API_URL");
  });
});
