import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import PaginaItens from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const item = {
  id: 1,
  prato_id: 10,
  prato_nome: "Feijoada",
  nome: "Feijoada",
  formato: "PF",
  gramas_por_porcao: 400,
  preco: "18.00",
  ativo: true,
};

const prato = { id: 10, nome: "Feijoada", proteina_id: 1, proteina_nome: "Carne", gramas_por_porcao: 400, ativo: true, itens_ativos: 1 };

function responder() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const corpo = String(url).endsWith("/itens") ? [item] : [prato];
    return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
  });
}

describe("UI-11 — itens de cardápio", () => {
  test("edição de item só altera preço", async () => {
    responder();
    render(<PaginaItens />);

    fireEvent.click(await screen.findByRole("button", { name: "Editar" }));

    expect(screen.getByRole("textbox", { name: "Preço" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Prato" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Formato" })).not.toBeInTheDocument();
    expect(screen.getByText("As vendas anteriores continuam com o preço antigo.")).toBeInTheDocument();
  });

  test("desativar item avisa a saída do cardápio", async () => {
    responder();
    render(<PaginaItens />);

    fireEvent.click(await screen.findByRole("button", { name: "Desativar" }));

    expect(
      screen.getByText("O item sai do cardápio e da tela de registro na hora."),
    ).toBeInTheDocument();
  });
});

test("duplicado desativado oferece reativar", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const corpo = String(url).endsWith("/itens") ? [{ ...item, ativo: false }] : [prato];
    return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
  });
  render(<PaginaItens />);

  fireEvent.click(await screen.findByRole("button", { name: "Novo item" }));
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "10" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Preço" }), { target: { value: "18.00" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

  expect(await screen.findByText("Já existe um item desativado para este prato e formato.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reativar" })).toBeInTheDocument();
});
