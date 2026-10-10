import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import PaginaPratos from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const prato = {
  id: 10,
  nome: "Feijoada",
  proteina_id: 1,
  proteina_nome: "Carne",
  gramas_por_porcao: 400,
  ativo: true,
  itens_ativos: 2,
};

test("editar gramagem mostra o aviso", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const corpo = String(url).includes("/proteinas") ? [{ id: 1, nome: "Carne", ativo: true, pratos_ativos: 1 }] : [prato];
    return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
  });
  render(<PaginaPratos />);

  fireEvent.click(await screen.findByRole("button", { name: "Editar" }));

  expect(screen.getByText("As vendas anteriores não mudam.")).toBeInTheDocument();
  expect(screen.getByText("A mesma gramagem vale para PF e marmita.")).toBeInTheDocument();
});

test("duplicado desativado oferece reativar", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const corpo = String(url).includes("/proteinas")
      ? [{ id: 1, nome: "Carne", ativo: true, pratos_ativos: 1 }]
      : [{ ...prato, nome: "Strogonoff", ativo: false, itens_ativos: 0 }];
    return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
  });
  render(<PaginaPratos />);

  fireEvent.click(await screen.findByRole("button", { name: "Novo prato" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Nome" }), { target: { value: " strogonoff " } });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Gramas por porção" }), { target: { value: "300" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

  expect(await screen.findByText("Já existe um prato desativado com esse nome.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reativar" })).toBeInTheDocument();
});
