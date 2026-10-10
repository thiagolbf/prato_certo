import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import VendasDaDataPagina from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const venda = {
  id: 1,
  horario: "2026-10-10T12:30:00Z",
  prato_nome: "Feijoada",
  proteina_nome: "Carne",
  formato: "PF",
  quantidade: 2,
  cancelada: false,
  preco_unitario: "18.00",
  valor_total: "36.00",
  autor: "Ana",
  cancelada_por: null,
  cancelada_em: null,
  motivo_cancelamento: null,
};

const cancelada = {
  ...venda,
  id: 2,
  prato_nome: "Strogonoff",
  cancelada: true,
  cancelada_por: "Bruno",
  cancelada_em: "2026-10-10T13:00:00Z",
  motivo_cancelamento: "Lançamento errado",
};

function renderizar() {
  return render(
    <ProvedorSessao valor={{ nome: "Bruno", perfil: "ADMIN", diaOperacional: "2026-10-10" }}>
      <VendasDaDataPagina />
    </ProvedorSessao>,
  );
}

function mockDados(vendas: unknown[]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    if (String(url).includes("/cancelar")) {
      return Promise.resolve(new Response(JSON.stringify({ id: 1 }), { status: 200 }));
    }
    return Promise.resolve(
      new Response(
        JSON.stringify({ data: "2026-10-10", vendas, total_unidades: 2, total_valor: "36.00" }),
        { status: 200 },
      ),
    );
  });
}

describe("UI-05 — vendas da data", () => {
  test("CA-50 — mostra todas as vendas com a cancelada marcada", async () => {
    mockDados([venda, cancelada]);
    renderizar();

    expect(await screen.findByText("2× Feijoada · PF")).toBeInTheDocument();
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
    expect(screen.getByText(/Cancelada por Bruno/)).toHaveTextContent("Lançamento errado");
    expect(screen.getAllByText(/R\$ 36,00/).length).toBeGreaterThan(0);
  });

  test("cancelar exige motivo", async () => {
    const fetchSpy = mockDados([venda]);
    renderizar();

    fireEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar venda" }));

    expect(screen.getByText("Informe o motivo do cancelamento.")).toBeInTheDocument();
    const envios = fetchSpy.mock.calls.filter(([url]) => String(url).includes("/cancelar"));
    expect(envios).toHaveLength(0);
  });

  test("409 mostra jaCancelada", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      if (String(url).includes("/cancelar")) {
        return Promise.resolve(new Response(JSON.stringify({ detail: "x" }), { status: 409 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ data: "2026-10-10", vendas: [venda], total_unidades: 2, total_valor: "36.00" }),
          { status: 200 },
        ),
      );
    });
    renderizar();

    fireEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Duplicada" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancelar venda" }));

    expect(await screen.findByText("Esta venda já foi cancelada.")).toBeInTheDocument();
  });
});

test("a data da URL é a data listada (atalho do fechamento)", async () => {
  window.history.pushState({}, "", "/vendas?data=2026-10-09");
  const fetchSpy = mockDados([venda]);
  renderizar();

  expect(await screen.findByText("2× Feijoada · PF")).toBeInTheDocument();
  const pedido = fetchSpy.mock.calls.map(([url]) => String(url)).find((u) => u.includes("/vendas?data="));
  expect(pedido).toContain("data=2026-10-09");
  window.history.pushState({}, "", "/");
});
