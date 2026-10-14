import { render, screen, within } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import type { ItemCardapio } from "@/lib/cardapio";

import { GradeCardapio } from "./GradeCardapio";

const item = (id: number, nome_prato: string, formato: "PF" | "MARMITA", preco: string): ItemCardapio => ({
  item_id: id,
  nome_prato,
  nome_proteina: "Frango",
  formato,
  gramas_por_porcao: 300,
  preco,
});

describe("GradeCardapio", () => {
  test("grade ordena pratos e fixa as colunas PF e Marmita", () => {
    render(
      <GradeCardapio
        itens={[
          item(1, "Strogonoff", "MARMITA", "22.00"),
          item(2, "Feijoada", "PF", "18.00"),
          item(3, "Arroz de forno", "PF", "20.00"),
          item(4, "Feijoada", "MARMITA", "16.00"),
        ]}
      />,
    );

    const linhas = screen.getAllByRole("row").slice(1);
    const nomes = linhas.map((linha) => within(linha).getByRole("rowheader").textContent);
    expect(nomes).toEqual(["Arroz de forno", "Feijoada", "Strogonoff"]);

    const cabecalho = screen.getAllByRole("columnheader").map((c) => c.textContent);
    expect(cabecalho).toEqual(["Prato", "PF", "Marmita"]);

    const feijoada = linhas[1];
    const celulas = within(feijoada).getAllByRole("cell");
    expect(celulas[0]).toHaveTextContent("PF");
    expect(celulas[0]).toHaveTextContent("R$ 18,00");
    expect(celulas[1]).toHaveTextContent("Marmita");
    expect(celulas[1]).toHaveTextContent("R$ 16,00");
  });
});
