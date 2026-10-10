import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import PaginaFechamento from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const vazio = {
  data: "2026-10-09",
  parcial: false,
  total_unidades: 0,
  unidades_por_item: [],
  unidades_por_prato: [],
  proteina_por_tipo: [],
  faturamento_por_formato: [],
  faturamento_total: "0.00",
  cancelamentos_posteriores: [],
};

function renderizar(corpo: unknown) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(corpo), { status: 200 }));
  return render(
    <ProvedorSessao valor={{ nome: "Bruno", perfil: "ADMIN", diaOperacional: "2026-10-10" }}>
      <PaginaFechamento />
    </ProvedorSessao>,
  );
}

describe("UI-07 — fechamento do dia", () => {
  test("CA-67 — mostra cancelamento posterior com autor e motivo", async () => {
    renderizar({
      ...vazio,
      faturamento_total: "18.00",
      cancelamentos_posteriores: [
        {
          venda_id: 9,
          prato_nome: "Feijoada",
          quantidade: 1,
          valor_total: "18.00",
          cancelada_em: "2026-10-10T13:00:00Z",
          cancelada_por: "Bruno",
          motivo_cancelamento: "Lançamento errado",
        },
      ],
    });

    expect(await screen.findByText(/cancelada por Bruno · Lançamento errado/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver vendas desta data" })).toHaveAttribute(
      "href",
      "/vendas?data=2026-10-09",
    );
  });

  test("formata gramas com kg", async () => {
    renderizar({
      ...vazio,
      total_unidades: 7,
      proteina_por_tipo: [{ proteina_nome: "Frango", gramas: 2100 }],
    });

    expect(await screen.findByText("2.100 g (2,1 kg)")).toBeInTheDocument();
  });

  test("mostra estado vazio sem vendas", async () => {
    renderizar(vazio);

    expect((await screen.findAllByText("Nenhum item vendido nesta data.")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("R$ 0,00").length).toBeGreaterThan(0);
  });

  test("unidades por prato separam PF e Marmita sem somar", async () => {
    renderizar({
      ...vazio,
      total_unidades: 5,
      unidades_por_item: [
        { item_id: 1, prato_nome: "Feijoada", formato: "PF", unidades: 3 },
        { item_id: 2, prato_nome: "Feijoada", formato: "MARMITA", unidades: 2 },
      ],
      unidades_por_prato: [{ prato_nome: "Feijoada", unidades: 5 }],
    });

    const linha = (await screen.findByRole("cell", { name: "Feijoada" })).closest("tr") as HTMLElement;
    const celulas = Array.from(linha.querySelectorAll("td")).map((td) => td.textContent);
    expect(celulas).toEqual(["Feijoada", "3", "2", "5"]);
  });
});
