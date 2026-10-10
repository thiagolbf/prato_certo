import { describe, expect, test } from "vitest";

import { lerPendencias, salvarPendencias, type Pendencia } from "./pendencias";

const pendencia: Pendencia = {
  chave: "0b6f2c1e-7d0a-4a52-9f0e-3c1f8e2a9b10",
  itemId: 1,
  nomePrato: "Feijoada",
  formato: "PF",
  quantidade: 2,
  usuario: "Ana",
  diaOperacional: "2026-10-10",
};

function armazenamentoEmMemoria() {
  const dados = new Map<string, string>();
  return {
    getItem: (k: string) => dados.get(k) ?? null,
    setItem: (k: string, v: string) => void dados.set(k, v),
  };
}

describe("pendências de venda", () => {
  test("pendência sobrevive a recarregar", () => {
    const armazenamento = armazenamentoEmMemoria();
    salvarPendencias([pendencia], armazenamento);

    // Recarregar a página é ler de novo o mesmo armazenamento.
    expect(lerPendencias(armazenamento)).toEqual([pendencia]);
  });

  test("armazenamento bloqueado não derruba a tela", () => {
    const bloqueado = {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    };

    expect(() => salvarPendencias([pendencia], bloqueado)).not.toThrow();
    expect(lerPendencias(bloqueado)).toEqual([]);
  });
});
