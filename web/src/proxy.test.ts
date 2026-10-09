// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "./proxy";

function requisicao(caminho: string, metodo: string, origem: string): NextRequest {
  return new NextRequest(`http://localhost${caminho}`, {
    method: metodo,
    headers: { "x-forwarded-for": origem },
  });
}

describe("proxy do limite de login (RN-37, CA-34)", () => {
  it("CA-34 — a 11ª tentativa de login da mesma origem recebe 429", () => {
    const origem = "203.0.113.50";
    for (let tentativa = 0; tentativa < 10; tentativa++) {
      expect(proxy(requisicao("/api/auth/login", "POST", origem)).status).not.toBe(429);
    }

    const recusada = proxy(requisicao("/api/auth/login", "POST", origem));

    expect(recusada.status).toBe(429);
  });

  it("CA-34 — outras rotas, como o registro de venda, não passam pelo limite", () => {
    const origem = "203.0.113.60";
    for (let tentativa = 0; tentativa < 15; tentativa++) {
      proxy(requisicao("/api/auth/login", "POST", origem));
    }

    expect(proxy(requisicao("/api/vendas", "POST", origem)).status).not.toBe(429);
    expect(proxy(requisicao("/api/auth/login", "GET", origem)).status).not.toBe(429);
  });
});
