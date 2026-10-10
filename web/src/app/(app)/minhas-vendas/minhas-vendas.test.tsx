import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import PaginaMinhasVendas from "./page";

afterEach(() => {
  vi.restoreAllMocks();
});

function responder(corpo: unknown) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(corpo), { status: 200 }));
}

const venda = {
  id: 1,
  horario: "2026-10-10T12:30:00Z",
  prato_nome: "Feijoada",
  proteina_nome: "Carne",
  formato: "PF",
  quantidade: 2,
  cancelada: false,
};

describe("UI-04 — minhas vendas", () => {
  test("CA-36 — lista não mostra preço nem valor", async () => {
    responder([venda]);
    render(<PaginaMinhasVendas />);

    expect(await screen.findByText("2× Feijoada · PF")).toBeInTheDocument();
    expect(screen.queryByText(/R\$/)).not.toBeInTheDocument();
  });

  test("CA-54 — venda cancelada aparece marcada", async () => {
    responder([{ ...venda, cancelada: true }]);
    render(<PaginaMinhasVendas />);

    expect(await screen.findByText("Cancelada")).toBeInTheDocument();
    expect(screen.getByText("2× Feijoada · PF")).toBeInTheDocument();
  });
});
