import { describe, expect, it } from "vitest";

import {
  formatarDataCurta,
  formatarGramas,
  formatarMesPorExtenso,
  formatarMoeda,
} from "./formato";

describe("formatação pt-BR (SPEC-UI 9)", () => {
  it("formata moeda com separador de milhar e vírgula decimal", () => {
    expect(formatarMoeda("1234.56")).toBe("R$ 1.234,56");
    expect(formatarMoeda("268.00")).toBe("R$ 268,00");
    expect(formatarMoeda("18")).toBe("R$ 18,00");
    expect(formatarMoeda("1000000.5")).toBe("R$ 1.000.000,50");
  });

  it("mostra a data como dd/mm", () => {
    expect(formatarDataCurta("2026-09-05")).toBe("05/09");
    expect(formatarDataCurta("2026-08-31")).toBe("31/08");
  });

  it("mostra o mês por extenso", () => {
    expect(formatarMesPorExtenso("2026-09")).toBe("setembro 2026");
    expect(formatarMesPorExtenso("2026-03")).toBe("março 2026");
  });

  it("mostra gramas com separador de milhar e kg a partir de 1.000 g", () => {
    expect(formatarGramas(450)).toBe("450 g");
    expect(formatarGramas(999)).toBe("999 g");
    expect(formatarGramas(1080)).toBe("1.080 g (1,1 kg)");
    expect(formatarGramas(2100)).toBe("2.100 g (2,1 kg)");
  });
});
