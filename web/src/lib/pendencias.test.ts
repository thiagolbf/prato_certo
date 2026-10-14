import { describe, expect, test } from "vitest";

import { conferirPendencias, lerPendencias, salvarPendencias, type Pendencia } from "./pendencias";

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

  test("CA-59 — pendência sobrevive à sessão expirada só para o mesmo usuário", () => {
    const doJoao = { ...pendencia, usuario: "joao" };

    const mesmoUsuario = conferirPendencias([doJoao], "joao", "2026-10-10");
    expect(mesmoUsuario.validas).toEqual([doJoao]);
    expect(mesmoUsuario.descartadas).toEqual([]);

    const outroUsuario = conferirPendencias([doJoao], "maria", "2026-10-10");
    expect(outroUsuario.validas).toEqual([]);
    expect(outroUsuario.descartadas).toEqual([doJoao]);
  });

  test("CA-60 — pendência de um dia não é enviada no dia seguinte", () => {
    const de22 = { ...pendencia, diaOperacional: "2026-09-22" };

    const resultado = conferirPendencias([de22], "Ana", "2026-09-23");

    expect(resultado.validas).toEqual([]);
    expect(resultado.descartadas).toEqual([de22]);
  });

  test("a conferência separa as válidas das descartadas sem perder nenhuma", () => {
    const valida = { ...pendencia, chave: "a" };
    const deOutroDia = { ...pendencia, chave: "b", diaOperacional: "2026-10-09" };
    const deOutroUsuario = { ...pendencia, chave: "c", usuario: "Bia" };

    const resultado = conferirPendencias([valida, deOutroDia, deOutroUsuario], "Ana", "2026-10-10");

    expect(resultado.validas).toEqual([valida]);
    expect(resultado.descartadas).toEqual([deOutroDia, deOutroUsuario]);
  });
});
