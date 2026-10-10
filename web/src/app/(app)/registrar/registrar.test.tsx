import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao, type Perfil } from "@/lib/sessao";

import PaginaRegistrar from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

function responder(corpo: unknown) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(corpo), { status: 200 }),
  );
}

function renderizar(perfil: Perfil) {
  return render(
    <ProvedorSessao valor={{ nome: "Ana", perfil, diaOperacional: "2026-10-10" }}>
      <PaginaRegistrar />
    </ProvedorSessao>,
  );
}

const itemPF = {
  item_id: 1,
  nome_prato: "Feijoada",
  nome_proteina: "Carne",
  formato: "PF",
  gramas_por_porcao: 400,
  preco: "18.00",
};

describe("UI-02 — registro", () => {
  test("CA-10 — primeiro uso mostra estado vazio sem itens tocáveis", async () => {
    responder({ data: "2026-10-10", tipo: "VAZIO", data_origem: null, itens: [] });
    renderizar("OPERADOR");

    expect(
      await screen.findByText("Chame o responsável para montar o cardápio do dia."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PF/ })).not.toBeInTheDocument();
  });

  test("herdado mostra a data de origem e o aviso só ao ADMIN", async () => {
    responder({ data: "2026-10-10", tipo: "HERDADO", data_origem: "2026-10-09", itens: [itemPF] });
    const { unmount } = renderizar("OPERADOR");

    expect(await screen.findByText("Herdado de 09/10")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Revisar cardápio" })).not.toBeInTheDocument();
    unmount();

    responder({ data: "2026-10-10", tipo: "HERDADO", data_origem: "2026-10-09", itens: [itemPF] });
    renderizar("ADMIN");

    expect(await screen.findByRole("link", { name: "Revisar cardápio" })).toBeInTheDocument();
  });
});
