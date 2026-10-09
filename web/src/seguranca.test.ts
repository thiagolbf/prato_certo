// @vitest-environment node
import { describe, expect, test } from "vitest";

import nextConfig, { cabecalhosDeSeguranca } from "../next.config";

function valorDo(cabecalhos: { key: string; value: string }[], nome: string): string {
  const encontrado = cabecalhos.find((cabecalho) => cabecalho.key === nome);
  if (!encontrado) throw new Error(`cabeçalho ausente: ${nome}`);
  return encontrado.value;
}

describe("cabeçalhos de segurança da Web (RN-43, CA-41)", () => {
  test("toda rota recebe os quatro cabeçalhos", async () => {
    const regras = await nextConfig.headers!();

    expect(regras).toEqual([
      { source: "/:path*", headers: expect.any(Array) },
    ]);
    const nomes = (regras[0].headers as { key: string }[]).map((h) => h.key);
    expect(nomes).toEqual([
      "Strict-Transport-Security",
      "X-Content-Type-Options",
      "X-Frame-Options",
      "Content-Security-Policy",
    ]);
  });

  test("HSTS, nosniff e DENY com os valores da arquitetura", () => {
    const cabecalhos = cabecalhosDeSeguranca(false);

    expect(valorDo(cabecalhos, "Strict-Transport-Security")).toBe(
      "max-age=31536000; includeSubDomains",
    );
    expect(valorDo(cabecalhos, "X-Content-Type-Options")).toBe("nosniff");
    expect(valorDo(cabecalhos, "X-Frame-Options")).toBe("DENY");
  });

  test("CSP restringe à própria origem e não abre domínio externo", () => {
    const csp = valorDo(cabecalhosDeSeguranca(false), "Content-Security-Policy");

    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).not.toMatch(/https?:\/\//);
  });

  test("unsafe-eval só existe em desenvolvimento", () => {
    const producao = valorDo(cabecalhosDeSeguranca(false), "Content-Security-Policy");
    const desenvolvimento = valorDo(cabecalhosDeSeguranca(true), "Content-Security-Policy");

    expect(producao).not.toContain("unsafe-eval");
    expect(desenvolvimento).toContain("'unsafe-eval'");
  });
});
