import { describe, expect, it } from "vitest";

import { LimiteDeRitmo } from "./limite-ritmo";

const MINUTO = 60_000;

describe("limite de ritmo por origem (RN-37, camada 2)", () => {
  it("CA-34 — disparo acima do ritmo é contido sem bloquear ninguém", () => {
    const limite = new LimiteDeRitmo(10, MINUTO);
    const agora = 1_000_000;

    for (let tentativa = 0; tentativa < 10; tentativa++) {
      expect(limite.permitir("203.0.113.7", agora + tentativa)).toBe(true);
    }
    // A 11ª tentativa da mesma origem, no mesmo minuto, é recusada.
    expect(limite.permitir("203.0.113.7", agora + 10)).toBe(false);
    // Outra origem continua livre: o limite é por origem.
    expect(limite.permitir("198.51.100.4", agora + 10)).toBe(true);
  });

  it("a janela libera depois de um minuto", () => {
    const limite = new LimiteDeRitmo(2, MINUTO);
    const agora = 2_000_000;

    expect(limite.permitir("origem", agora)).toBe(true);
    expect(limite.permitir("origem", agora + 1)).toBe(true);
    expect(limite.permitir("origem", agora + 2)).toBe(false);
    // Passado um minuto desde os primeiros disparos, a origem volta a passar.
    expect(limite.permitir("origem", agora + MINUTO + 1)).toBe(true);
  });
});
